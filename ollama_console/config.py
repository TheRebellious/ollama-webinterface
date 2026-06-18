import argparse
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = PROJECT_ROOT / "index.html"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    ollama_url: str
    index_path: Path
    debug_shutdown: bool


def parse_args():
    parser = argparse.ArgumentParser(description="Web interface for a local Ollama server.")
    parser.add_argument("--host", default=os.getenv("OLLAMA_UI_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("OLLAMA_UI_PORT", "8080")))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL))
    parser.add_argument(
        "--debug-shutdown",
        action="store_true",
        help="Show a UI button that stops this server. Use only while debugging.",
    )
    return parser.parse_args()


def build_config(args) -> ServerConfig:
    return ServerConfig(
        host=args.host,
        port=args.port,
        ollama_url=args.ollama_url,
        index_path=DEFAULT_INDEX_PATH,
        debug_shutdown=args.debug_shutdown,
    )
