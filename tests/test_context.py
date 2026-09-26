"""Unit tests for context recommendation algorithms and metadata extraction (TE-001, MA-002)."""
import pytest

from ollama_console.context import (
    find_context_limit,
    estimate_kv_bytes_per_token,
    estimate_context_memory_budget,
    estimate_model_bytes,
    floor_step,
    DEFAULT_KV_BYTES_PER_TOKEN,
    MIN_CONTEXT,
)


class TestContextCalculations:
    """Test context recommendation components."""

    def test_find_context_limit_from_dict(self):
        data = {"context_length": 8192}
        assert find_context_limit(data) == 8192

    def test_find_context_limit_nested(self):
        data = {"model_info": {"llama.context_length": 16384}}
        assert find_context_limit(data) == 16384

    def test_find_context_limit_none_when_missing(self):
        data = {"other_key": 100}
        assert find_context_limit(data) is None

    def test_estimate_kv_bytes_per_token_with_layers_heads(self):
        model_info = {
            "llama.block_count": 32,
            "llama.attention.head_count_kv": 8,
            "llama.attention.key_length": 128,
        }
        # 2 * 32 * 8 * 128 * 2 = 131072 bytes = 128 KB
        kv = estimate_kv_bytes_per_token(model_info)
        assert kv == 131072

    def test_estimate_kv_bytes_fallback_to_default(self):
        model_info = {}
        assert estimate_kv_bytes_per_token(model_info) == DEFAULT_KV_BYTES_PER_TOKEN

    def test_floor_step_rounds_down(self):
        assert floor_step(4000) == 3584  # 7 * 512 = 3584
        assert floor_step(4096) == 4096

    def test_estimate_model_bytes_llama_8b_q4(self):
        details = {
            "parameter_size": "8.0B",
            "quantization_level": "Q4_K_M",
        }
        # 8 * 10^9 * 4 / 8 * 1.20 = 4.8 * 10^9 bytes ~ 4.8 GB
        size = estimate_model_bytes(details)
        assert 4_000_000_000 <= size <= 6_000_000_000

    def test_estimate_context_memory_budget_ram_fallback(self):
        system_info = {
            "memory": {"availableBytes": 16 * 1024 * 1024 * 1024},  # 16 GB
            "gpu": [],
        }
        running = {"models": []}
        budget = estimate_context_memory_budget(system_info, running, "llama3.1")
        # 50% of 16 GB = 8 GB
        assert budget == 8 * 1024 * 1024 * 1024
