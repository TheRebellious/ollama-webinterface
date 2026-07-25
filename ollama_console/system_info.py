import os
import platform
import shutil
import subprocess
import ctypes
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
    if platform.system().lower() == "windows":
        return get_windows_memory_info()

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


def get_windows_memory_info():
    native = get_windows_memory_info_native()
    if native["totalBytes"] is not None:
        return native

    try:
        result = subprocess.run(
            [
                "wmic",
                "OS",
                "get",
                "FreePhysicalMemory,TotalVisibleMemorySize",
                "/Value",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return {"totalBytes": None, "availableBytes": None, "usedPercent": None}

    values = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = parse_int(value.strip())

    total = values.get("TotalVisibleMemorySize")
    available = values.get("FreePhysicalMemory")
    if total is not None:
        total *= 1024
    if available is not None:
        available *= 1024

    used_percent = None
    if total and available is not None:
        used_percent = round(((total - available) / total) * 100, 1)

    return {
        "totalBytes": total,
        "availableBytes": available,
        "usedPercent": used_percent,
    }


def get_windows_memory_info_native():
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)

    try:
        ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except (AttributeError, OSError):
        ok = False

    if not ok:
        return {"totalBytes": None, "availableBytes": None, "usedPercent": None}

    return {
        "totalBytes": int(status.ullTotalPhys),
        "availableBytes": int(status.ullAvailPhys),
        "usedPercent": round(float(status.dwMemoryLoad), 1),
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
    return get_nvidia_gpu_info() + get_amd_gpu_info()


def get_nvidia_gpu_info():
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
            "vendor": "NVIDIA",
            "name": name,
            "memoryTotalMb": parse_int(total_mb),
            "memoryUsedMb": parse_int(used_mb),
            "utilizationPercent": parse_int(utilization),
        })

    return gpus


def get_amd_gpu_info():
    for detector in (get_amd_gpu_info_from_amd_smi, get_amd_gpu_info_from_rocm_smi):
        gpus = detector()
        if gpus:
            return gpus

    return get_amd_gpu_info_from_sysfs()


def get_amd_gpu_info_from_amd_smi():
    if not shutil.which("amd-smi"):
        return []

    try:
        result = subprocess.run(
            ["amd-smi", "list"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    gpus = []
    for line in result.stdout.splitlines():
        if "gpu" not in line.lower():
            continue
        name = line.split(":", 1)[-1].strip(" -") or line.strip()
        gpus.append({
            "vendor": "AMD",
            "name": name,
            "memoryTotalMb": None,
            "memoryUsedMb": None,
            "utilizationPercent": None,
        })
    return gpus


def get_amd_gpu_info_from_rocm_smi():
    if not shutil.which("rocm-smi"):
        return []

    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname", "--showuse", "--showmemuse"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    gpus = {}
    for line in result.stdout.splitlines():
        lowered = line.lower()
        card = parse_card_id(line)
        if card is None:
            continue

        gpu = gpus.setdefault(card, {
            "vendor": "AMD",
            "name": f"AMD GPU {card}",
            "memoryTotalMb": None,
            "memoryUsedMb": None,
            "utilizationPercent": None,
        })

        if "card series" in lowered or "card model" in lowered:
            gpu["name"] = line.split(":", 1)[-1].strip() or gpu["name"]
        elif "gpu use" in lowered or "gpu busy" in lowered:
            gpu["utilizationPercent"] = parse_percent(line)
        elif "vram" in lowered and ("use" in lowered or "%" in line):
            gpu["utilizationPercent"] = gpu["utilizationPercent"]

    return list(gpus.values())


def get_amd_gpu_info_from_sysfs():
    drm_path = Path("/sys/class/drm")
    if not drm_path.exists():
        return []

    gpus = []
    for card in sorted(drm_path.glob("card[0-9]*")):
        vendor_path = card / "device" / "vendor"
        try:
            vendor = vendor_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue

        if vendor != "0x1002":
            continue

        name = read_first_existing(card / "device" / "product_name", card / "device" / "product_number")
        gpus.append({
            "vendor": "AMD",
            "name": name or f"AMD GPU {card.name}",
            "memoryTotalMb": None,
            "memoryUsedMb": None,
            "utilizationPercent": None,
        })

    return gpus


def parse_card_id(line):
    for token in line.replace(":", " ").split():
        if token.lower().startswith("gpu["):
            return token.strip("[]")
        if token.lower().startswith("card"):
            return token.strip(":")
    return None


def parse_percent(line):
    for token in line.replace("%", " %").split():
        if token.endswith("%"):
            return parse_int(token.rstrip("%"))
        if token.isdigit() and "%" in line:
            return parse_int(token)
    return None


def read_first_existing(*paths):
    for path in paths:
        try:
            value = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if value:
            return value
    return None


def parse_int(value):
    try:
        return int(value)
    except ValueError:
        return None
