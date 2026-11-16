"""Audits of a plugin's models: their textures, their UVs and what the compiler shipped."""

import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from modelkit import game
from modelkit.source2 import modeldoc

# Textures this small are flat colours, such as glow and team colours; audits skip them.
SOLID_COLOUR = 64


@dataclass(frozen=True)
class Material:
    model: str
    name: str
    keys: dict[str, str]
    accent: bool
    """A team colour or glow, flat on purpose."""


def find_models(plugin: str, only: list[str] | None = None) -> list[Path]:
    """The plugin's model folders, or just those named in `only`."""
    root = game.models_dir(plugin)
    if not root.is_dir():
        raise FileNotFoundError(f"no models at {root}")
    folders = sorted(p for p in root.iterdir() if p.is_dir())
    if only:
        missing = set(only) - {p.name for p in folders}
        if missing:
            raise FileNotFoundError(f"no model folder {', '.join(sorted(missing))} in {root}")
        folders = [p for p in folders if p.name in only]
    return folders


def read_materials(folder: Path) -> list[Material]:
    swapped = {
        PurePosixPath(path).name
        for vmdl in folder.glob("*.vmdl")
        for path in modeldoc.read_vmdl(vmdl).swapped
    }
    materials = []
    for vmat in sorted(folder.glob("*.vmat")):
        keys = modeldoc.read_vmat(vmat)
        accent = vmat.name in swapped or keys.get("F_SELF_ILLUM") == "1"
        materials.append(Material(folder.name, vmat.name, keys, accent))
    return materials


def find_source(plugin: str, addon_path: str) -> Path | None:
    """The source file behind an addon path such as "models/x/x_color.png", if the plugin has it."""
    path = game.plugin_dir(plugin) / "content" / addon_path
    return path if path.is_file() else None


def read_png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        header = f.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", header[16:24])


def shipped_size(size: tuple[int, int], cap: int | None) -> tuple[int, int]:
    """The size the compiler writes: the longest side clamped to `cap`, aspect kept."""
    if not cap or max(size) <= cap:
        return size
    factor = cap / max(size)
    return max(1, round(size[0] * factor)), max(1, round(size[1] * factor))
