"""Tests for the HTTP handler security layer (SE-001, SE-002, SE-003, SE-005)."""
import base64
import io
import json
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.request
import urllib.error

import pytest

from ollama_console.config import ServerConfig
from ollama_console.handler import OllamaConsoleHandler, _sanitize_filename


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_config(**overrides) -> ServerConfig:
    """Build a minimal ServerConfig for testing."""
    defaults = dict(
        host="127.0.0.1",
        port=0,
        ollama_url="http://127.0.0.1:11434",
        index_path=PROJECT_ROOT / "index.html",
        manifest_path=PROJECT_ROOT / "manifest.webmanifest",
        icon_path=PROJECT_ROOT / "icon.svg",
        styles_path=PROJECT_ROOT / "styles.css",
        debug_shutdown=False,
        upload_max_bytes=10 * 1024 * 1024,
        log_path=PROJECT_ROOT / "ollama-console.log",
        auth_token=None,
        rate_limit_per_minute=0,
        cors_origin="",
    )
    defaults.update(overrides)
    return ServerConfig(**defaults)


class _LiveServer:
    """Start a real ThreadingHTTPServer on a random port for integration tests."""

    def __init__(self, config: ServerConfig):
        handler_class = type("H", (OllamaConsoleHandler,), {"config": config})
        self.server = HTTPServer(("127.0.0.1", 0), handler_class)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def url(self, path=""):
        return f"http://127.0.0.1:{self.port}{path}"

    def stop(self):
        self.server.shutdown()


def _do_request(url, method="GET", headers=None, data=None):
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


# ---------------------------------------------------------------------------
# SE-002: Filename sanitisation
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_normal_filename_unchanged(self):
        assert _sanitize_filename("report.docx") == "report.docx"

    def test_strips_directory_components(self):
        result = _sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert result == ".._.._etc_passwd" or "passwd" in result or ".." not in result

    def test_strips_null_bytes(self):
        result = _sanitize_filename("file\x00name.txt")
        assert "\x00" not in result

    def test_strips_path_separators(self):
        result = _sanitize_filename("dir/subdir/file.txt")
        # os.path.basename gives "file.txt"
        assert result == "file.txt"

    def test_windows_path_stripped(self):
        result = _sanitize_filename("C:\\Users\\attacker\\evil.docx")
        assert result == "evil.docx"

    def test_empty_filename_returns_empty(self):
        result = _sanitize_filename("")
        assert result == ""

    def test_dotdot_segment_replaced(self):
        result = _sanitize_filename("foo..bar.docx")
        # ".." is matched as a single pattern → replaced with single underscore
        assert result == "foo_bar.docx"

    def test_unicode_characters_replaced(self):
        result = _sanitize_filename("filé.docx")
        # non-ASCII replaced with underscore
        assert result == "fil_.docx"


# ---------------------------------------------------------------------------
# SE-001: Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    def setup_method(self):
        config = _make_config(auth_token="secret-token-abc")
        self.srv = _LiveServer(config)

    def teardown_method(self):
        self.srv.stop()

    def test_api_endpoint_requires_auth(self):
        status, body, _ = _do_request(self.srv.url("/api/config"))
        assert status == 401
        data = json.loads(body)
        assert "error" in data

    def test_correct_token_grants_access(self):
        status, body, _ = _do_request(
            self.srv.url("/api/config"),
            headers={"Authorization": "Bearer secret-token-abc"},
        )
        assert status == 200
        data = json.loads(body)
        assert "debugShutdown" in data

    def test_wrong_token_rejected(self):
        status, body, _ = _do_request(
            self.srv.url("/api/config"),
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert status == 401

    def test_malformed_auth_header_rejected(self):
        status, body, _ = _do_request(
            self.srv.url("/api/config"),
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert status == 401

    def test_static_files_accessible_without_auth(self):
        """Static files (index.html, CSS) must not be gated by auth."""
        status, _, _ = _do_request(self.srv.url("/"))
        assert status == 200

    def test_www_authenticate_header_present(self):
        _, _, headers = _do_request(self.srv.url("/api/tags"))
        assert "www-authenticate" in {k.lower() for k in headers}

    def test_no_auth_config_allows_all(self):
        """When no auth_token is configured, all endpoints are public."""
        config = _make_config(auth_token=None)
        srv = _LiveServer(config)
        try:
            status, _, _ = _do_request(srv.url("/api/config"))
            assert status == 200
        finally:
            srv.stop()


# ---------------------------------------------------------------------------
# SE-003: Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def setup_method(self):
        config = _make_config(rate_limit_per_minute=3)
        self.srv = _LiveServer(config)

    def teardown_method(self):
        self.srv.stop()

    def test_requests_within_limit_succeed(self):
        for _ in range(3):
            status, _, _ = _do_request(self.srv.url("/api/config"))
            assert status == 200

    def test_requests_beyond_limit_rejected(self):
        for _ in range(3):
            _do_request(self.srv.url("/api/config"))
        status, body, _ = _do_request(self.srv.url("/api/config"))
        assert status == 429
        data = json.loads(body)
        assert "error" in data

    def test_rate_limit_headers_present(self):
        _, _, headers = _do_request(self.srv.url("/api/config"))
        header_names_lower = {k.lower() for k in headers}
        assert "x-ratelimit-limit" in header_names_lower
        assert "x-ratelimit-remaining" in header_names_lower
        assert "x-ratelimit-reset" in header_names_lower

    def test_retry_after_header_on_429(self):
        for _ in range(3):
            _do_request(self.srv.url("/api/config"))
        _, _, headers = _do_request(self.srv.url("/api/config"))
        header_names_lower = {k.lower() for k in headers}
        assert "retry-after" in header_names_lower

    def test_static_files_not_rate_limited(self):
        """Static file serving should bypass rate limiting."""
        config = _make_config(rate_limit_per_minute=1)
        srv = _LiveServer(config)
        try:
            _do_request(srv.url("/api/config"))  # exhaust limit
            # Static files should still be accessible
            status, _, _ = _do_request(srv.url("/"))
            assert status == 200
        finally:
            srv.stop()


# ---------------------------------------------------------------------------
# SE-005: CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:
    def test_cors_header_set_when_configured(self):
        config = _make_config(cors_origin="https://example.com")
        srv = _LiveServer(config)
        try:
            _, _, headers = _do_request(srv.url("/api/config"))
            header_names_lower = {k.lower(): v for k, v in headers.items()}
            assert "access-control-allow-origin" in header_names_lower
            assert header_names_lower["access-control-allow-origin"] == "https://example.com"
        finally:
            srv.stop()

    def test_cors_header_absent_when_not_configured(self):
        config = _make_config(cors_origin="")
        srv = _LiveServer(config)
        try:
            _, _, headers = _do_request(srv.url("/api/config"))
            header_names_lower = {k.lower() for k in headers}
            assert "access-control-allow-origin" not in header_names_lower
        finally:
            srv.stop()

    def test_options_preflight_returns_204(self):
        config = _make_config(cors_origin="*")
        srv = _LiveServer(config)
        try:
            status, _, _ = _do_request(srv.url("/api/chat"), method="OPTIONS")
            assert status == 204
        finally:
            srv.stop()

    def test_security_headers_always_present(self):
        """X-Content-Type-Options and X-Frame-Options are always sent."""
        config = _make_config()
        srv = _LiveServer(config)
        try:
            _, _, headers = _do_request(srv.url("/api/config"))
            header_names_lower = {k.lower(): v for k, v in headers.items()}
            assert "x-content-type-options" in header_names_lower
            assert "x-frame-options" in header_names_lower
        finally:
            srv.stop()


# ---------------------------------------------------------------------------
# SE-004: Sensitive field logging filter
# ---------------------------------------------------------------------------

class TestSensitiveFieldFilter:
    def test_auth_token_redacted(self):
        import logging
        from ollama_console.server import _SensitiveFieldFilter

        filt = _SensitiveFieldFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg='auth_token: "super-secret-value"', args=(), exc_info=None,
        )
        filt.filter(record)
        assert "super-secret-value" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_password_redacted_in_args(self):
        import logging
        from ollama_console.server import _SensitiveFieldFilter

        filt = _SensitiveFieldFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="config: %s", args=('password: "hunter2"',), exc_info=None,
        )
        filt.filter(record)
        assert "hunter2" not in str(record.args)

    def test_non_sensitive_field_untouched(self):
        import logging
        from ollama_console.server import _SensitiveFieldFilter

        filt = _SensitiveFieldFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="model: llama3.1, status: running", args=(), exc_info=None,
        )
        filt.filter(record)
        assert "llama3.1" in record.msg
        assert "running" in record.msg
