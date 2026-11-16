"""What the compiler shipped: each source texture against its compiled .vtex_c."""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from modelkit import game
from modelkit.audit import SOLID_COLOUR, find_source, read_materials, read_png_size
from modelkit.source2 import vtex

# Roughness and metalness have no .vtex_c of their own: csgo_complex packs them into others.
SHIPPED_KEYS = (
    "TextureColor",
    "TextureNormal",
    "TextureAmbientOcclusion",
    "TextureSelfIllumMask",
    "TextureTranslucency",
)


@dataclass
class CompiledReport:
    model: str
    texture: str
    source: tuple[int, int]
    shipped: tuple[int, int] | None
    problems: list[str] = field(default_factory=list)


def find_compiled(plugin: str, addon_path: str) -> Path | None:
    """The newest .vtex_c compiled from `addon_path`; the compiler names it <stem>_png_<hash>."""
    source = PurePosixPath(addon_path)
    folder = game.compiled_addon(plugin) / source.parent
    found = sorted(
        folder.glob(f"{source.stem}_{source.suffix.lstrip('.')}_*.vtex_c"),
        key=lambda p: p.stat().st_mtime,
    )
    return found[-1] if found else None


def audit(plugin: str, folders: list[Path]) -> list[CompiledReport]:
    reports, seen = [], set()
    for folder in folders:
        for material in read_materials(folder):
            for key in SHIPPED_KEYS:
                addon_path = material.keys.get(key, "")
                source = find_source(plugin, addon_path)
                if source is None or addon_path in seen:
                    continue
                seen.add(addon_path)
                size = read_png_size(source)
                if max(size) <= SOLID_COLOUR:
                    continue
                compiled = find_compiled(plugin, addon_path)
                if compiled is None:
                    reports.append(
                        CompiledReport(folder.name, addon_path, size, None, ["not compiled"])
                    )
                    continue
                texture = vtex.read(compiled)
                shipped = (texture.width, texture.height)
                report = CompiledReport(folder.name, addon_path, size, shipped)
                if max(shipped) < max(size):
                    report.problems.append("downscaled by the compiler")
                elif compiled.stat().st_mtime < source.stat().st_mtime:
                    report.problems.append("older than its source")
                reports.append(report)
    return reports
