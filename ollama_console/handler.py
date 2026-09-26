import json
import logging
import mimetypes
import os
import re
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler

from .file_extract import FileExtractionError, extract_uploaded_file
from .context import get_context_recommendation
from .ollama import proxy_ollama
from .rate_limiter import RateLimiter
from .system_info import get_system_info


LOGGER = logging.getLogger("ollama_console")

# A shared rate limiter instance.  Limit and window are applied from config
# when the first request arrives.  The instance is replaced if config changes.
_rate_limiter: RateLimiter | None = None
_rate_limiter_lock = threading.Lock()

# Filename sanitisation: only printable ASCII, no path separators, no null bytes.
_UNSAFE_FILENAME_RE = re.compile(r'[^\x20-\x7E]|[/\\:*?"<>|]|\.\.')


def _get_rate_limiter(config) -> RateLimiter | None:
    """Return the shared RateLimiter, (re-)creating it from config if needed."""
    global _rate_limiter  # noqa: PLW0603
    if not config.rate_limit_per_minute:
        return None
    with _rate_limiter_lock:
        if _rate_limiter is None or _rate_limiter.limit != config.rate_limit_per_minute:
            _rate_limiter = RateLimiter(limit=config.rate_limit_per_minute, window=60)
        return _rate_limiter


def _sanitize_filename(filename: str) -> str:
    """Remove or replace characters that are unsafe in filenames.

    Strips path components, replaces unsafe characters, and trims whitespace.
    Returns an empty string if no safe characters remain.
    """
    # Drop directory components
    basename = os.path.basename(filename.replace("\\", "/"))
    # Replace unsafe characters with underscores
    safe = _UNSAFE_FILENAME_RE.sub("_", basename)
    return safe.strip()


class OllamaConsoleHandler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        LOGGER.info("%s - %s", self.address_string(), format % args)

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------

    def _add_security_headers(self):
        """Add CORS and cache-control security headers (SE-005)."""
        if self.config.cors_origin:
            self.send_header("Access-Control-Allow-Origin", self.config.cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Vary", "Origin")
        # Defensive security headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")

    def _check_auth(self) -> bool:
        """Return True when the request is authorised (SE-001).

        Authentication is skipped entirely when no auth_token is configured.
        When a token *is* configured, the request must carry:
          Authorization: Bearer <token>
        """
        if not self.config.auth_token:
            return True  # Auth disabled

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        return auth_header[len("Bearer "):].strip() == self.config.auth_token

    def _check_rate_limit(self) -> bool:
        """Return True when the client IP is within its rate limit (SE-003).

        Adds standard rate-limit response headers to every API response.
        """
        limiter = _get_rate_limiter(self.config)
        if limiter is None:
            return True  # Rate limiting disabled

        client_ip = self.address_string()
        allowed, remaining, reset = limiter.is_allowed(client_ip)
        self.send_header("X-RateLimit-Limit", str(self.config.rate_limit_per_minute))
        self.send_header("X-RateLimit-Remaining", str(remaining))
        self.send_header("X-RateLimit-Reset", str(reset))
        return allowed

    def _handle_api_security(self) -> bool:
        """Run auth + rate-limit checks for API endpoints.

        Sends a 401 or 429 and returns False if the request should be rejected.
        Returns True if the request may proceed.

        NOTE: Headers must NOT have been started yet when this is called.
        """
        if not self._check_auth():
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("WWW-Authenticate", "Bearer realm=\"ollama-console\"")
            self._add_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
            return False

        # We pre-open the response here only if rate-limited; otherwise the
        # caller sends the response.  Use a two-phase approach: check first,
        # send 429 only on rejection.
        limiter = _get_rate_limiter(self.config)
        if limiter is not None:
            client_ip = self.address_string()
            allowed, remaining, reset = limiter.is_allowed(client_ip)
            if not allowed:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-RateLimit-Limit", str(self.config.rate_limit_per_minute))
                self.send_header("X-RateLimit-Remaining", "0")
                self.send_header("X-RateLimit-Reset", str(reset))
                self.send_header("Retry-After", str(reset))
                self._add_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Rate limit exceeded"}).encode("utf-8"))
                return False

        return True

    # ------------------------------------------------------------------
    # CORS preflight
    # ------------------------------------------------------------------

    def do_OPTIONS(self):
        """Handle CORS preflight requests (SE-005)."""
        self.send_response(204)
        self._add_security_headers()
        self.end_headers()

    # ------------------------------------------------------------------
    # GET routes
    # ------------------------------------------------------------------

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
            if not self._handle_api_security():
                return
            self.send_json({
                "debugShutdown": self.config.debug_shutdown,
                "uploadMaxBytes": self.config.upload_max_bytes,
                "authEnabled": bool(self.config.auth_token),
            })
            return

        if self.path == "/api/tags":
            if not self._handle_api_security():
                return
            proxy_ollama(self, "GET", "/api/tags")
            return

        if self.path == "/api/ps":
            if not self._handle_api_security():
                return
            proxy_ollama(self, "GET", "/api/ps")
            return

        if self.path == "/api/system":
            if not self._handle_api_security():
                return
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

    # ------------------------------------------------------------------
    # POST routes
    # ------------------------------------------------------------------

    def do_POST(self):
        if self.path == "/api/chat":
            if not self._handle_api_security():
                return
            proxy_ollama(self, "POST", "/api/chat")
            return

        if self.path == "/api/show":
            if not self._handle_api_security():
                return
            proxy_ollama(self, "POST", "/api/show")
            return

        if self.path == "/api/context-recommendation":
            if not self._handle_api_security():
                return
            self.context_recommendation()
            return

        if self.path == "/api/preload":
            if not self._handle_api_security():
                return
            self.preload_model()
            return

        if self.path == "/api/shutdown":
            if not self._handle_api_security():
                return
            self.shutdown_server()
            return

        if self.path == "/api/extract":
            if not self._handle_api_security():
                return
            self.extract_file()
            return

        self.send_error(404, "Not found")

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

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
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload, status=200):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(content)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Request body must be valid JSON") from error

    # ------------------------------------------------------------------
    # Endpoint implementations
    # ------------------------------------------------------------------

    def extract_file(self):
        """Handle file text-extraction requests (SE-002 - filename sanitisation)."""
        try:
            payload = self.read_json()
            raw_name = payload.get("filename", "")
            safe_name = _sanitize_filename(str(raw_name))
            if not safe_name:
                raise FileExtractionError("Filename contains no safe characters")
            result = extract_uploaded_file(
                safe_name,
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
