"""Tests for Ollama upstream proxying and error recovery (CR-001, CI-001)."""
import io
import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from ollama_console.config import ServerConfig
from ollama_console.ollama import proxy_ollama


class DummyHandler:
    """Mock HTTP request handler for proxy testing."""

    def __init__(self, ollama_url="http://127.0.0.1:11434"):
        self.config = MagicMock()
        self.config.ollama_url = ollama_url
        self.headers = {"Content-Length": "0"}
        self.rfile = io.BytesIO(b"")
        self.wfile = io.BytesIO()
        self.status_code = None
        self.response_headers = {}
        self.json_payload = None

    def send_response(self, code):
        self.status_code = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def send_json(self, payload, status=200):
        self.status_code = status
        self.json_payload = payload

    def _add_security_headers(self):
        pass


class TestOllamaProxy:
    """Unit tests for proxy_ollama error classification and behavior."""

    @patch("urllib.request.urlopen")
    def test_successful_proxy_get(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read.side_effect = [b'{"models":[]}', b""]
        mock_urlopen.return_value.__enter__.return_value = mock_response

        handler = DummyHandler()
        proxy_ollama(handler, "GET", "/api/tags")

        assert handler.status_code == 200
        assert handler.wfile.getvalue() == b'{"models":[]}'

    @patch("urllib.request.urlopen")
    def test_upstream_http_error_passed_through(self, mock_urlopen):
        mock_error = urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/show",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b'{"error":"model not found"}'),
        )
        mock_urlopen.side_effect = mock_error

        handler = DummyHandler()
        proxy_ollama(handler, "POST", "/api/show", request_body=b'{"model":"missing"}')

        assert handler.status_code == 404
        assert handler.wfile.getvalue() == b'{"error":"model not found"}'

    @patch("urllib.request.urlopen")
    def test_connection_refused_returns_502_structured_json(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(
            reason=ConnectionRefusedError("Connection refused")
        )

        handler = DummyHandler()
        proxy_ollama(handler, "POST", "/api/chat", request_body=b'{"model":"test"}')

        assert handler.status_code == 502
        assert handler.json_payload is not None
        assert handler.json_payload.get("code") == "CONNECTION_FAILED"
        assert "Ensure the Ollama service is running" in handler.json_payload.get("detail", "")

    @patch("urllib.request.urlopen")
    def test_timeout_returns_504_structured_json(self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout("timed out")

        handler = DummyHandler()
        proxy_ollama(handler, "POST", "/api/chat", request_body=b'{"model":"test"}')

        assert handler.status_code == 504
        assert handler.json_payload is not None
        assert handler.json_payload.get("code") == "TIMEOUT"
        assert "timed out" in handler.json_payload.get("error", "").lower()
