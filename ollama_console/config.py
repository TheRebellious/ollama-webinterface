import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = PROJECT_ROOT / "index.html"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "manifest.webmanifest"
DEFAULT_ICON_PATH = PROJECT_ROOT / "icon.svg"
DEFAULT_STYLES_PATH = PROJECT_ROOT / "styles.css"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    ollama_url: str
    index_path: Path
    manifest_path: Path
    icon_path: Path
    styles_path: Path
    debug_shutdown: bool


def parse_args():
    parser = argparse.ArgumentParser(description="Web interface for a local Ollama server.")
    parser.add_argument("--config", default=os.getenv("OLLAMA_CONSOLE_CONFIG", str(DEFAULT_CONFIG_PATH)))
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--ollama-url")
    parser.add_argument(
        "--debug-shutdown",
        action="store_true",
        help="Show a UI button that stops this server. Use only while debugging.",
    )
    return parser.parse_args()


def build_config(args) -> ServerConfig:
    file_config = load_config_file(Path(args.config))

    host = first_value(args.host, os.getenv("OLLAMA_UI_HOST"), file_config.get("host"), "0.0.0.0")
    port = first_value(args.port, parse_int(os.getenv("OLLAMA_UI_PORT")), file_config.get("port"), 8080)
    ollama_url = first_value(
        args.ollama_url,
        os.getenv("OLLAMA_URL"),
        file_config.get("ollama_url"),
        DEFAULT_OLLAMA_URL,
    )
    debug_shutdown = bool(first_value(
        args.debug_shutdown if args.debug_shutdown else None,
        parse_bool(os.getenv("OLLAMA_DEBUG_SHUTDOWN")),
        file_config.get("debug_shutdown"),
        False,
    ))

    return ServerConfig(
        host=str(host),
        port=int(port),
        ollama_url=str(ollama_url),
        index_path=DEFAULT_INDEX_PATH,
        manifest_path=DEFAULT_MANIFEST_PATH,
        icon_path=DEFAULT_ICON_PATH,
        styles_path=DEFAULT_STYLES_PATH,
        debug_shutdown=debug_shutdown,
    )


def load_config_file(path: Path):
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Could not read config file {path}: {error}") from error

    if not isinstance(data, dict):
        raise SystemExit(f"Config file {path} must contain a JSON object")

    allowed_keys = {"host", "port", "ollama_url", "debug_shutdown"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise SystemExit(f"Unknown config keys in {path}: {', '.join(unknown_keys)}")

    return data


def first_value(*values):
    for value in values:
        if value is not None:
            return value
    return None


def parse_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise SystemExit(f"Expected integer value, got {value!r}") from error


def parse_bool(value):
    if value is None or value == "":
        return None

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise SystemExit(f"Expected boolean value, got {value!r}")
