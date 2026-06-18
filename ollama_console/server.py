from http.server import ThreadingHTTPServer

from .config import build_config, parse_args
from .handler import OllamaConsoleHandler


def make_handler(config):
    class ConfiguredHandler(OllamaConsoleHandler):
        pass

    ConfiguredHandler.config = config
    return ConfiguredHandler


def run_server(config):
    handler = make_handler(config)
    server = ThreadingHTTPServer((config.host, config.port), handler)

    print(f"Ollama Console listening on http://{config.host}:{config.port}")
    print(f"Proxying Ollama at {config.ollama_url}")
    if config.debug_shutdown:
        print("Debug shutdown enabled at POST /api/shutdown")

    try:
        server.serve_forever()
    finally:
        server.server_close()
        print("Ollama Console stopped")


def main():
    args = parse_args()
    config = build_config(args)
    run_server(config)
