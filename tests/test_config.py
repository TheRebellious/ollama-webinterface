"""Tests for server configuration validation and loading (CR-006, CI-002)."""
import argparse
from pathlib import Path
import pytest

from ollama_console.config import build_config, validate_config, ServerConfig


class TestConfigValidation:
    """Test validate_config parameter constraints."""

    def test_valid_configuration_passes(self):
        # Should not raise any exception
        validate_config(
            host="127.0.0.1",
            port=8080,
            ollama_url="http://127.0.0.1:11434",
            upload_max_mb=10,
            rate_limit_per_minute=60,
        )

    def test_empty_host_rejected(self):
        with pytest.raises(ValueError, match="host"):
            validate_config(
                host="",
                port=8080,
                ollama_url="http://127.0.0.1:11434",
                upload_max_mb=10,
                rate_limit_per_minute=0,
            )

    def test_invalid_port_low_rejected(self):
        with pytest.raises(ValueError, match="port"):
            validate_config(
                host="0.0.0.0",
                port=0,
                ollama_url="http://127.0.0.1:11434",
                upload_max_mb=10,
                rate_limit_per_minute=0,
            )

    def test_invalid_port_high_rejected(self):
        with pytest.raises(ValueError, match="port"):
            validate_config(
                host="0.0.0.0",
                port=70000,
                ollama_url="http://127.0.0.1:11434",
                upload_max_mb=10,
                rate_limit_per_minute=0,
            )

    def test_invalid_ollama_url_scheme_rejected(self):
        with pytest.raises(ValueError, match="ollama_url"):
            validate_config(
                host="0.0.0.0",
                port=8080,
                ollama_url="ftp://127.0.0.1:11434",
                upload_max_mb=10,
                rate_limit_per_minute=0,
            )

    def test_invalid_ollama_url_no_host_rejected(self):
        with pytest.raises(ValueError, match="ollama_url"):
            validate_config(
                host="0.0.0.0",
                port=8080,
                ollama_url="http://",
                upload_max_mb=10,
                rate_limit_per_minute=0,
            )

    def test_upload_max_mb_bounds_checked(self):
        with pytest.raises(ValueError, match="upload_max_mb"):
            validate_config(
                host="0.0.0.0",
                port=8080,
                ollama_url="http://127.0.0.1:11434",
                upload_max_mb=0,
                rate_limit_per_minute=0,
            )

        with pytest.raises(ValueError, match="upload_max_mb"):
            validate_config(
                host="0.0.0.0",
                port=8080,
                ollama_url="http://127.0.0.1:11434",
                upload_max_mb=2048,
                rate_limit_per_minute=0,
            )

    def test_negative_rate_limit_rejected(self):
        with pytest.raises(ValueError, match="rate_limit_per_minute"):
            validate_config(
                host="0.0.0.0",
                port=8080,
                ollama_url="http://127.0.0.1:11434",
                upload_max_mb=10,
                rate_limit_per_minute=-5,
            )


class TestBuildConfig:
    """Test build_config with CLI args and defaults."""

    def test_default_config_creation(self, tmp_path):
        dummy_config = tmp_path / "nonexistent.json"
        args = argparse.Namespace(
            config=str(dummy_config),
            host=None,
            port=None,
            ollama_url=None,
            log_file=None,
            debug_shutdown=False,
            auth_token=None,
            rate_limit_per_minute=None,
            cors_origin=None,
        )
        config = build_config(args)
        assert isinstance(config, ServerConfig)
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.ollama_url == "http://127.0.0.1:11434"
        assert config.upload_max_bytes == 10 * 1024 * 1024
        assert config.auth_token is None

    def test_cli_override_applied(self, tmp_path):
        dummy_config = tmp_path / "nonexistent.json"
        args = argparse.Namespace(
            config=str(dummy_config),
            host="127.0.0.1",
            port=9090,
            ollama_url="http://remote-ollama:11434",
            log_file=None,
            debug_shutdown=True,
            auth_token="token-xyz",
            rate_limit_per_minute=120,
            cors_origin="*",
        )
        config = build_config(args)
        assert config.host == "127.0.0.1"
        assert config.port == 9090
        assert config.ollama_url == "http://remote-ollama:11434"
        assert config.debug_shutdown is True
        assert config.auth_token == "token-xyz"
        assert config.rate_limit_per_minute == 120
        assert config.cors_origin == "*"
