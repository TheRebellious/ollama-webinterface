"""Hardware-based context window recommendation algorithm for Ollama models.

Estimates the optimal token context window (num_ctx) that fits comfortably in
available host RAM or GPU VRAM without risking out-of-memory errors (OOM).
"""
import json
import math
import re
import urllib.request

# Metadata keys in Ollama model details that define context capacity
CONTEXT_KEYS = {"context_length", "num_ctx"}

# Minimum context floor (512 tokens) to guarantee functional prompting
MIN_CONTEXT = 512

# Context granularity step (rounds down to multiples of 512 for cache efficiency)
CONTEXT_STEP = 512

# Default estimated key-value (KV) cache memory footprint per token if layer details are missing
# (128 KB/token corresponds to a typical 8B-14B parameter model with 32 layers, GQA)
DEFAULT_KV_BYTES_PER_TOKEN = 128 * 1024

# Fraction of available host RAM safe to allocate for Ollama KV cache (50%)
RAM_MEMORY_FRACTION = 0.50

# Fraction of available free GPU VRAM safe to allocate for Ollama KV cache (95%)
GPU_MEMORY_FRACTION = 0.95

# Absolute minimum memory safety reserve for context allocation (256 MB)
MIN_CONTEXT_MEMORY_RESERVE_BYTES = 256 * 1024 * 1024


def get_context_recommendation(config, model: str, system_info: dict) -> dict:
    """Compute context window recommendation based on model architecture and free hardware memory.

    Args:
        config: Server configuration containing Ollama upstream URL.
        model: Ollama model name string.
        system_info: Dictionary containing host CPU, RAM, and GPU statistics.

    Returns:
        Dictionary with modelContext, recommendedContext, kvBytesPerToken, memoryBudgetBytes.
    """
    show = ollama_json(config.ollama_url, "/api/show", {"model": model})
    running = ollama_json(config.ollama_url, "/api/ps", None)
    model_info = show.get("model_info") or {}
    model_context = (
        find_context_limit(model_info)
        or find_context_limit(show.get("details"))
        or find_context_limit(show)
    )
    kv_bytes = estimate_kv_bytes_per_token(model_info)
    memory_budget = estimate_context_memory_budget(system_info, running, model, show.get("details") or {})

    if model_context is None:
        model_context = 4096

    recommended = max(
        MIN_CONTEXT,
        min(model_context, floor_step(memory_budget / kv_bytes)),
    )
    return {
        "modelContext": model_context,
        "recommendedContext": recommended,
        "kvBytesPerToken": kv_bytes,
        "memoryBudgetBytes": memory_budget,
        "source": "hardware",
    }


def ollama_json(base_url: str, path: str, payload: dict | None) -> dict:
    """Make a JSON request to an Ollama endpoint and parse the response."""
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_context_limit(value) -> int | None:
    """Recursively search a nested dictionary or list for known context length keys."""
    if isinstance(value, list):
        for item in value:
            nested = find_context_limit(item)
            if nested is not None:
                return nested
        return None
    if not isinstance(value, dict):
        return None
    for key, item in value.items():
        normalized = str(key).lower()
        if normalized in CONTEXT_KEYS or normalized.endswith(".context_length"):
            number = parse_number(item)
            if number is not None and number >= MIN_CONTEXT:
                return int(number)
        nested = find_context_limit(item)
        if nested is not None:
            return nested
    return None


def estimate_kv_bytes_per_token(model_info: dict) -> int:
    """Estimate KV cache memory consumption in bytes per token from GGUF metadata."""
    layers = find_metadata_number(model_info, "block_count")
    embedding = find_metadata_number(model_info, "embedding_length")
    kv_heads = find_metadata_number(model_info, "attention.head_count_kv")
    head_dim = find_metadata_number(model_info, "attention.key_length")

    if layers and kv_heads and head_dim:
        return int(2 * layers * kv_heads * head_dim * 2)
    if layers and embedding:
        heads = find_metadata_number(model_info, "attention.head_count") or 1
        return int(2 * layers * embedding / heads * 2)
    return DEFAULT_KV_BYTES_PER_TOKEN


def find_metadata_number(value, suffix: str) -> float | None:
    """Search dictionary keys ending with suffix and parse numeric value."""
    if not isinstance(value, dict):
        return None
    for key, item in value.items():
        if str(key).lower().endswith(suffix.lower()):
            number = parse_number(item)
            if number is not None and number > 0:
                return number
        nested = find_metadata_number(item, suffix)
        if nested is not None:
            return nested
    return None


def estimate_context_memory_budget(system_info: dict, running: dict, model: str, details: dict | None = None) -> int:
    """Calculate maximum safe memory in bytes to dedicate to KV cache."""
    memory = system_info.get("memory") or {}
    available_ram = parse_number(memory.get("availableBytes")) or 0
    ram_budget = int(available_ram * RAM_MEMORY_FRACTION)

    gpu_budget = 0
    for gpu in system_info.get("gpu") or []:
        total = parse_number(gpu.get("memoryTotalMb"))
        used = parse_number(gpu.get("memoryUsedMb")) or 0
        if total:
            gpu_budget += max(0, total * 1024 * 1024 - used * 1024 * 1024)
    gpu_budget = int(gpu_budget * GPU_MEMORY_FRACTION)

    runtime = next(
        (item for item in (running.get("models") or []) if item.get("name") == model),
        None,
    )
    processor = str((runtime or {}).get("processor", "")).lower()
    if processor == "cpu" or not gpu_budget:
        return max(ram_budget, MIN_CONTEXT_MEMORY_RESERVE_BYTES)
    if runtime is None:
        gpu_budget -= estimate_model_bytes(details or {})
    return max(gpu_budget, MIN_CONTEXT_MEMORY_RESERVE_BYTES)


def estimate_model_bytes(details: dict) -> int:
    """Estimate weights footprint in bytes from parameter size and quantization level."""
    value = str(details.get("parameter_size", ""))
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([TGMK]?)B", value, re.IGNORECASE)
    if not match:
        return 0
    parameter_count = float(match.group(1))
    scale = {"": 10**9, "k": 10**3, "m": 10**6, "g": 10**9, "t": 10**12}[match.group(2).lower()]
    bits = 16
    quantization = str(details.get("quantization_level", "")).lower()
    quant_match = re.search(r"q(\d)", quantization)
    if quant_match:
        bits = int(quant_match.group(1))
    return int(parameter_count * scale * bits / 8 * 1.20)


def floor_step(value: float) -> int:
    """Round down value to the nearest integer multiple of CONTEXT_STEP."""
    if not math.isfinite(value):
        return MIN_CONTEXT
    return int(value // CONTEXT_STEP) * CONTEXT_STEP


def parse_number(value) -> float | None:
    """Parse string or float number safely, returning None on failure."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
