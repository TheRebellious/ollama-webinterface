import urllib.error
import urllib.request
import logging


LOGGER = logging.getLogger("ollama_console")


def proxy_ollama(handler, method, upstream_path, request_body=None):
    body = None
    if method == "POST":
        if request_body is None:
            length = int(handler.headers.get("Content-Length", "0"))
            body = handler.rfile.read(length)
        else:
            body = request_body

    request = urllib.request.Request(
        handler.config.ollama_url.rstrip("/") + upstream_path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=600) as upstream:
            handler.send_response(upstream.status)
            content_type = upstream.headers.get("Content-Type", "application/json")
            handler.send_header("Content-Type", content_type)
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()

            while True:
                chunk = upstream.read(8192)
                if not chunk:
                    break
                handler.wfile.write(chunk)
                handler.wfile.flush()
    except urllib.error.HTTPError as error:
        LOGGER.warning("Ollama returned HTTP %s for %s", error.code, upstream_path)
        error_body = error.read()
        LOGGER.warning("Ollama error response for %s: %s", upstream_path, error_body.decode("utf-8", errors="replace"))
        handler.send_response(error.code)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(error_body)
    except Exception as error:
        LOGGER.exception("Could not reach Ollama for %s", upstream_path)
        payload = {"error": "Could not reach Ollama", "detail": str(error)}
        handler.send_json(payload, status=502)
