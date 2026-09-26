import logging
import logging.handlers
import sys
import threading
from http.server import ThreadingHTTPServer

from .config import build_config, parse_args
from .handler import OllamaConsoleHandler


LOGGER = logging.getLogger("ollama_console")


class _SensitiveFieldFilter(logging.Filter):
    """Scrub sensitive field patterns from log records (SE-004, CI-003).

    Replaces the *value* of common sensitive keys (password, token, key,
    secret, authorization) in the formatted message so that credentials are
    not written to disk even if an exception propagates unexpected data.
    """

    import re as _re
    _PATTERN = _re.compile(
        r'("?(?:password|auth[_-]?token|api[_-]?key|secret|authorization)"?\s*[:=]\s*)"?[^\s,"}{]{3,}"?',
        _re.IGNORECASE,
    )

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.msg = self._PATTERN.sub(r'\1[REDACTED]', str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._PATTERN.sub(r'\1[REDACTED]', str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._PATTERN.sub(r'\1[REDACTED]', str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def configure_logging(log_path):
    """Write server logs to the console and an append-only log file (CI-003).

    Applies a sensitive-field filter to both handlers so credentials are
    never written to the log file or console output (SE-004).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"
    )
    sensitive_filter = _SensitiveFieldFilter()

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)

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
    if config.auth_token:
        LOGGER.info("API authentication enabled (Bearer token required)")
    if config.rate_limit_per_minute:
        LOGGER.info("Rate limiting enabled: %d requests/minute per IP", config.rate_limit_per_minute)
    if config.cors_origin:
        LOGGER.info("CORS origin: %s", config.cors_origin)

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
