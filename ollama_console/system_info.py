import os
import platform
import shutil
import subprocess
from pathlib import Path


def get_system_info(root_path: Path):
    return {
        "host": platform.node() or "unknown",
        "platform": platform.platform(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(root_path),
        "load": get_load_info(),
        "uptimeSeconds": get_uptime_seconds(),
        "gpu": get_gpu_info(),
    }


def get_cpu_info():
    return {
        "model": read_cpu_model(),
        "cores": os.cpu_count() or 0,
    }


def read_cpu_model():
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        try:
            for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass

    return platform.processor() or platform.machine() or "unknown"


def get_memory_info():
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return {"totalBytes": None, "availableBytes": None, "usedPercent": None}

    values = {}
    try:
        for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return {"totalBytes": None, "availableBytes": None, "usedPercent": None}

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used_percent = None
    if total and available is not None:
        used_percent = round(((total - available) / total) * 100, 1)

    return {
        "totalBytes": total,
        "availableBytes": available,
        "usedPercent": used_percent,
    }


def get_disk_info(root_path: Path):
    usage = shutil.disk_usage(root_path)
    return {
        "path": str(root_path),
        "totalBytes": usage.total,
        "freeBytes": usage.free,
        "usedPercent": round((usage.used / usage.total) * 100, 1) if usage.total else None,
    }


def get_load_info():
    if not hasattr(os, "getloadavg"):
        return {"one": None, "five": None, "fifteen": None}

    one, five, fifteen = os.getloadavg()
    return {
        "one": round(one, 2),
        "five": round(five, 2),
        "fifteen": round(fifteen, 2),
    }


def get_uptime_seconds():
    uptime = Path("/proc/uptime")
    if not uptime.exists():
        return None

    try:
        return int(float(uptime.read_text(encoding="utf-8").split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def get_gpu_info():
    if not shutil.which("nvidia-smi"):
        return []

    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2, check=True)
    except (OSError, subprocess.SubprocessError):
        return []

    gpus = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue

        name, total_mb, used_mb, utilization = parts
        gpus.append({
            "name": name,
            "memoryTotalMb": parse_int(total_mb),
            "memoryUsedMb": parse_int(used_mb),
            "utilizationPercent": parse_int(utilization),
        })

    return gpus


def parse_int(value):
    try:
        return int(value)
    except ValueError:
        return None
