"""Ollama upstream API proxying with error classification, recovery, and timeouts."""
import http.client
import json
import logging
import socket
import time
import urllib.error
import urllib.request

LOGGER = logging.getLogger("ollama_console")

# Retryable GET endpoints for transient connection drops
RETRYABLE_METHODS = {"GET"}
MAX_RETRIES = 1
INITIAL_BACKOFF = 0.5


def proxy_ollama(handler, method, upstream_path, request_body=None):
    """Proxy HTTP requests to the configured Ollama upstream instance.

    Handles connection recovery, distinguishes transient vs permanent failures,
    and returns standardized JSON errors (CR-001, CI-001).
    """
    body = None
    if method == "POST":
        if request_body is None:
            length = int(handler.headers.get("Content-Length", "0"))
            body = handler.rfile.read(length)
        else:
            body = request_body

    target_url = handler.config.ollama_url.rstrip("/") + upstream_path
    retries = MAX_RETRIES if method in RETRYABLE_METHODS else 0

    for attempt in range(retries + 1):
        request = urllib.request.Request(
            target_url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )

        try:
            # 600s timeout allows long model generations while preventing dead hangs
            with urllib.request.urlopen(request, timeout=600) as upstream:
                handler.send_response(upstream.status)
                content_type = upstream.headers.get("Content-Type", "application/json")
                handler.send_header("Content-Type", content_type)
                handler.send_header("Cache-Control", "no-store")
                if hasattr(handler, "_add_security_headers"):
                    handler._add_security_headers()
                handler.end_headers()

                while True:
                    chunk = upstream.read(8192)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
                return

        except urllib.error.HTTPError as error:
            # Upstream Ollama returned an HTTP error (e.g. 404 Model Not Found, 500)
            LOGGER.warning("Ollama returned HTTP %s for %s", error.code, upstream_path)
            error_body = error.read()
            LOGGER.warning(
                "Ollama error response for %s: %s",
                upstream_path,
                error_body.decode("utf-8", errors="replace"),
            )
            handler.send_response(error.code)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Cache-Control", "no-store")
            if hasattr(handler, "_add_security_headers"):
                handler._add_security_headers()
            handler.end_headers()
            handler.wfile.write(error_body)
            return

        except (socket.timeout, TimeoutError) as error:
            LOGGER.error("Timeout communicating with Ollama for %s: %s", upstream_path, error)
            payload = {
                "error": "Ollama request timed out",
                "detail": f"Timed out waiting for response from {handler.config.ollama_url}",
                "code": "TIMEOUT",
            }
            handler.send_json(payload, status=504)
            return

        except (urllib.error.URLError, ConnectionRefusedError, http.client.RemoteDisconnected, OSError) as error:
            # Check if retry is appropriate for idempotent requests
            if attempt < retries:
                LOGGER.info("Transient error reaching Ollama, retrying in %.1fs: %s", INITIAL_BACKOFF, error)
                time.sleep(INITIAL_BACKOFF)
                continue

            LOGGER.warning("Could not reach Ollama at %s for %s: %s", handler.config.ollama_url, upstream_path, error)
            payload = {
                "error": "Could not reach Ollama",
                "detail": f"Failed to connect to Ollama at {handler.config.ollama_url}. Ensure the Ollama service is running.",
                "code": "CONNECTION_FAILED",
            }
            handler.send_json(payload, status=502)
            return

        except Exception as error:  # noqa: BLE001
            LOGGER.exception("Unexpected error proxying to Ollama for %s", upstream_path)
            payload = {
                "error": "Unexpected proxy error",
                "detail": str(error),
                "code": "INTERNAL_ERROR",
            }
            handler.send_json(payload, status=502)
            return
