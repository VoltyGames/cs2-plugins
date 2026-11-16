"""Where things live: the repository, a plugin's content, the CS2 client and Blender."""

import os
import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

lazy from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[4]
DEFAULT_CLIENT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
)
BLENDER_INSTALLS = Path(r"C:\Program Files\Blender Foundation")
SETTINGS = ("CS2_CLIENT_PATH", "CS2_SERVER_PATH", "BLENDER_PATH")


@cache
def settings() -> dict[str, str]:
    """The paths set in the repository's .env; the environment overrides them."""
    values = {k: v for k, v in dotenv_values(REPO / ".env").items() if k in SETTINGS and v}
    return values | {k: os.environ[k] for k in SETTINGS if os.environ.get(k)}


def client() -> Path:
    return Path(settings().get("CS2_CLIENT_PATH") or DEFAULT_CLIENT)


def compiler() -> Path:
    return client() / "game" / "bin" / "win64" / "resourcecompiler.exe"


def plugin_dir(plugin: str) -> Path:
    return REPO / "plugins" / plugin


def models_dir(plugin: str) -> Path:
    return plugin_dir(plugin) / "content" / "models" / plugin


def compiled_addon(plugin: str) -> Path:
    """Where the Workshop Tools write the plugin's compiled addon."""
    return client() / "game" / "csgo_addons" / plugin


def read_texture_cap() -> int | None:
    """The largest texture the public Workshop Tools compile, from the client's gameinfo.gi."""
    gameinfo = client() / "game" / "csgo" / "gameinfo.gi"
    if not gameinfo.exists():
        return None
    found = re.search(r'PublicToolsDefaultMaxRes\s+"(\d+)"', gameinfo.read_text(errors="ignore"))
    return int(found.group(1)) if found else None


def find_blender() -> Path | None:
    """BLENDER_PATH, then blender on PATH, then the newest install under Program Files."""
    if configured := settings().get("BLENDER_PATH"):
        return Path(configured)
    if on_path := shutil.which("blender"):
        return Path(on_path)
    installs = sorted(
        BLENDER_INSTALLS.glob("Blender */blender.exe"),
        key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)],
    )
    return installs[-1] if installs else None


def find_running_cs2() -> list[str]:
    """Process ids of running cs2.exe instances; installing into a running game fails."""
    if os.name != "nt":
        return []
    tasks = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq cs2.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
    )
    return [
        line.split(",")[1].strip('"') for line in tasks.stdout.splitlines() if "cs2.exe" in line
    ]
