import urllib.error
import urllib.request


def proxy_ollama(handler, method, upstream_path):
    body = None
    if method == "POST":
        length = int(handler.headers.get("Content-Length", "0"))
        body = handler.rfile.read(length)

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
        handler.send_response(error.code)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(error.read())
    except Exception as error:
        payload = {"error": "Could not reach Ollama", "detail": str(error)}
        handler.send_json(payload, status=502)
