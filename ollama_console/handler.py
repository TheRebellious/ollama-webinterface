import json
import logging
import mimetypes
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler

from .file_extract import FileExtractionError, extract_uploaded_file
from .context import get_context_recommendation
from .ollama import proxy_ollama
from .system_info import get_system_info


LOGGER = logging.getLogger("ollama_console")


class OllamaConsoleHandler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_file(self.config.index_path, "text/html; charset=utf-8")
            return

        if self.path == "/styles.css":
            self.serve_file(self.config.styles_path, "text/css; charset=utf-8")
            return

        if self.path == "/manifest.webmanifest":
            self.serve_file(self.config.manifest_path, "application/manifest+json")
            return

        if self.path == "/icon.svg":
            self.serve_file(self.config.icon_path, "image/svg+xml")
            return

        if self.path.startswith("/assets/"):
            self.serve_asset()
            return

        if self.path == "/api/config":
            self.send_json({
                "debugShutdown": self.config.debug_shutdown,
                "uploadMaxBytes": self.config.upload_max_bytes,
            })
            return

        if self.path == "/api/tags":
            proxy_ollama(self, "GET", "/api/tags")
            return

        if self.path == "/api/ps":
            proxy_ollama(self, "GET", "/api/ps")
            return

        if self.path == "/api/system":
            self.send_json(get_system_info(self.config.index_path.parent))
            return

        self.send_error(404, "Not found")

    def serve_asset(self):
        root = self.config.index_path.parent.resolve()
        relative_path = self.path.split("?", 1)[0].lstrip("/")
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root / "assets")
        except ValueError:
            self.send_error(404, "Not found")
            return

        content_type, _ = mimetypes.guess_type(candidate.name)
        self.serve_file(candidate, content_type or "application/octet-stream")

    def do_POST(self):
        if self.path == "/api/chat":
            proxy_ollama(self, "POST", "/api/chat")
            return

        if self.path == "/api/show":
            proxy_ollama(self, "POST", "/api/show")
            return

        if self.path == "/api/context-recommendation":
            self.context_recommendation()
            return

        if self.path == "/api/preload":
            self.preload_model()
            return

        if self.path == "/api/shutdown":
            self.shutdown_server()
            return

        if self.path == "/api/extract":
            self.extract_file()
            return

        self.send_error(404, "Not found")

    def serve_file(self, path, content_type):
        try:
            content = path.read_bytes()
        except OSError as error:
            LOGGER.exception("Could not read static file %s", path)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Could not read {path.name}: {error}".encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload, status=200):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Request body must be valid JSON") from error

    def extract_file(self):
        try:
            payload = self.read_json()
            result = extract_uploaded_file(
                payload.get("filename", ""),
                payload.get("contentBase64", ""),
                self.config.upload_max_bytes,
            )
        except (ValueError, FileExtractionError) as error:
            LOGGER.warning("File extraction request rejected: %s", error)
            self.send_json({"error": str(error)}, status=400)
            return

        self.send_json(result)

    def context_recommendation(self):
        try:
            payload = self.read_json()
            model = str(payload.get("model", "")).strip()
            if not model:
                raise ValueError("A model is required")
            result = get_context_recommendation(
                self.config,
                model,
                get_system_info(self.config.index_path.parent),
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as error:
            self.send_json({"error": str(error)}, status=502)
            return

        self.send_json(result)

    def preload_model(self):
        try:
            payload = self.read_json()
            model = str(payload.get("model", "")).strip()
            if not model:
                raise ValueError("A model is required")
            request_body = json.dumps({
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "num_ctx": int(payload.get("context", 4096)),
                },
            }).encode("utf-8")
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, status=400)
            return

        proxy_ollama(self, "POST", "/api/generate", request_body)

    def shutdown_server(self):
        if not self.config.debug_shutdown:
            self.send_json({"error": "Debug shutdown is disabled"}, status=403)
            return

        self.send_json({"ok": True, "message": "Server shutting down"})
        threading.Thread(target=self.server.shutdown, daemon=True).start()
