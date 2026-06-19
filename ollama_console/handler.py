import json
import threading
from http.server import BaseHTTPRequestHandler

from .file_extract import FileExtractionError, extract_uploaded_file
from .ollama import proxy_ollama
from .system_info import get_system_info


class OllamaConsoleHandler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

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

    def do_POST(self):
        if self.path == "/api/chat":
            proxy_ollama(self, "POST", "/api/chat")
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
            self.send_json({"error": str(error)}, status=400)
            return

        self.send_json(result)

    def shutdown_server(self):
        if not self.config.debug_shutdown:
            self.send_json({"error": "Debug shutdown is disabled"}, status=403)
            return

        self.send_json({"ok": True, "message": "Server shutting down"})
        threading.Thread(target=self.server.shutdown, daemon=True).start()
