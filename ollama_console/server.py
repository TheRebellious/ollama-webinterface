import logging
import sys
import threading
from http.server import ThreadingHTTPServer

from .config import build_config, parse_args
from .handler import OllamaConsoleHandler


LOGGER = logging.getLogger("ollama_console")


def configure_logging(log_path):
    """Write server logs to the console and an append-only log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"
    )
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(console_handler)
    LOGGER.propagate = False


class LoggingThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        LOGGER.exception("Unhandled request error from %s", client_address[0])


def make_handler(config):
    class ConfiguredHandler(OllamaConsoleHandler):
        pass

    ConfiguredHandler.config = config
    return ConfiguredHandler


def run_server(config):
    handler = make_handler(config)
    server = LoggingThreadingHTTPServer((config.host, config.port), handler)

    LOGGER.info("Ollama Console listening on http://%s:%s", config.host, config.port)
    LOGGER.info("Proxying Ollama at %s", config.ollama_url)
    if config.debug_shutdown:
        LOGGER.info("Debug shutdown enabled at POST /api/shutdown")

    try:
        server.serve_forever()
    finally:
        server.server_close()
        LOGGER.info("Ollama Console stopped")


def main():
    args = parse_args()
    config = build_config(args)
    configure_logging(config.log_path)
    LOGGER.info("Logging to %s", config.log_path)

    def log_unhandled_exception(exc_type, exc_value, traceback):
        LOGGER.critical("Unhandled exception", exc_info=(exc_type, exc_value, traceback))

    sys.excepthook = log_unhandled_exception
    threading.excepthook = lambda args: LOGGER.critical(
        "Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )
    run_server(config)
