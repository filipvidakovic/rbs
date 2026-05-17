# oblak/config.py
import os
from pathlib import Path

OBLAK_DIR = Path.home() / ".oblak"
CONFIG_FILE = OBLAK_DIR / "config"
DEFAULT_SERVER = "http://localhost:8080"


def get_server_url() -> str:
    env = os.environ.get("OBLAK_SERVER")
    if env:
        return env.rstrip("/")

    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if line.startswith("OBLAK_SERVER="):
                return line.split("=", 1)[1].strip().rstrip("/")

    return DEFAULT_SERVER


def save_server_url(url: str) -> None:
    OBLAK_DIR.mkdir(exist_ok=True)
    lines = []
    if CONFIG_FILE.exists():
        lines = [
            l for l in CONFIG_FILE.read_text().splitlines()
            if not l.startswith("OBLAK_SERVER=")
        ]
    lines.append(f"OBLAK_SERVER={url}")
    CONFIG_FILE.write_text("\n".join(lines) + "\n")