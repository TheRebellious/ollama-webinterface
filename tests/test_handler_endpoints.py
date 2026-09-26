"""Integration tests for Ollama Console HTTP API endpoints (TE-002, TE-003)."""
import base64
import io
import json
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ollama_console.config import ServerConfig
from ollama_console.handler import OllamaConsoleHandler
from tests.test_file_extract import _create_mock_docx

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_config(**overrides) -> ServerConfig:
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


class _TestServer:
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


def _request(url, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed, dict(e.headers)


class TestApiEndpoints:
    """Test standard HTTP endpoint responses and error cases."""

    def setup_method(self):
        self.srv = _TestServer(_make_config(debug_shutdown=False))

    def teardown_method(self):
        self.srv.stop()

    def test_get_system_endpoint(self):
        status, data, _ = _request(self.srv.url("/api/system"))
        assert status == 200
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data

    def test_extract_endpoint_success(self):
        docx = _create_mock_docx("Integrated extraction content")
        b64 = base64.b64encode(docx).decode("ascii")
        status, data, _ = _request(
            self.srv.url("/api/extract"),
            method="POST",
            payload={"filename": "doc.docx", "contentBase64": b64},
        )
        assert status == 200
        assert "Integrated extraction content" in data.get("content", "")

    def test_extract_endpoint_unsupported_file_returns_400(self):
        status, data, _ = _request(
            self.srv.url("/api/extract"),
            method="POST",
            payload={"filename": "malware.exe", "contentBase64": "AAAA"},
        )
        assert status == 400
        assert "error" in data

    def test_context_recommendation_missing_model_returns_502(self):
        status, data, _ = _request(
            self.srv.url("/api/context-recommendation"),
            method="POST",
            payload={"model": ""},
        )
        assert status == 502
        assert "error" in data

    def test_preload_model_missing_model_returns_400(self):
        status, data, _ = _request(
            self.srv.url("/api/preload"),
            method="POST",
            payload={"model": ""},
        )
        assert status == 400
        assert "error" in data

    def test_shutdown_endpoint_forbidden_when_disabled(self):
        status, data, _ = _request(self.srv.url("/api/shutdown"), method="POST", payload={})
        assert status == 403
        assert "disabled" in data.get("error", "").lower()

    def test_shutdown_endpoint_allowed_when_enabled(self):
        srv = _TestServer(_make_config(debug_shutdown=True))
        try:
            status, data, _ = _request(srv.url("/api/shutdown"), method="POST", payload={})
            assert status == 200
            assert data.get("ok") is True
        finally:
            srv.stop()
