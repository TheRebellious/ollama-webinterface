"""Unit tests for system information and hardware detection (TE-001)."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ollama_console.system_info import (
    get_system_info,
    get_cpu_info,
    get_disk_info,
    parse_percent,
    parse_float_percent,
    parse_lspci_gpu_line,
    dedupe_gpus,
)


class TestSystemInfo:
    """Test hardware spec detection and string parsers."""

    def test_get_system_info_structure(self, tmp_path):
        info = get_system_info(tmp_path)
        assert "host" in info
        assert "cpu" in info
        assert "memory" in info
        assert "disk" in info
        assert "load" in info
        assert "gpu" in info
        assert isinstance(info["gpu"], list)

    def test_get_cpu_info(self):
        cpu = get_cpu_info()
        assert "model" in cpu
        assert "cores" in cpu
        assert isinstance(cpu["cores"], int)
        assert cpu["cores"] >= 0

    def test_get_disk_info(self, tmp_path):
        disk = get_disk_info(tmp_path)
        assert "totalBytes" in disk
        assert "freeBytes" in disk
        assert disk["totalBytes"] > 0

    def test_parse_percent_helper(self):
        assert parse_percent("GPU 0: 45%") == 45
        assert parse_percent("Memory usage: 82 %") == 82
        assert parse_percent("No percentage here") is None

    def test_parse_float_percent_helper(self):
        assert parse_float_percent("45.6") == 45.6
        assert parse_float_percent("12,4") == 12.4
        assert parse_float_percent("invalid") is None

    def test_parse_lspci_gpu_line(self):
        line = "0000:01:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi 21 [Radeon RX 6800/6800 XT / 6900 XT]"
        address, name = parse_lspci_gpu_line(line)
        assert address == "0000:01:00.0"
        assert "Navi 21" in name or "Radeon" in name

    def test_dedupe_gpus(self):
        gpus = [
            {"pciAddress": "0000:01:00.0", "name": "Card A"},
            {"pciAddress": "0000:01:00.0", "name": "Card A Duplicate"},
            {"pciAddress": "0000:02:00.0", "name": "Card B"},
        ]
        deduped = dedupe_gpus(gpus)
        assert len(deduped) == 2
        assert deduped[0]["name"] == "Card A"
        assert deduped[1]["name"] == "Card B"
