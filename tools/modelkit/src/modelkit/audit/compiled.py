"""What the compiler shipped: each source texture against its compiled .vtex_c."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from modelkit import game
from modelkit.audit import Report, format_size
from modelkit.models import ModelFolder, is_solid_colour, read_image_size
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
class CompiledReport(Report):
    COLUMNS = ("model", "texture", "source", "shipped")
    model: str
    texture: str
    source: tuple[int, int]
    shipped: tuple[int, int] | None

    def cells(self) -> list[str]:
        return [self.model, self.texture, format_size(self.source), format_size(self.shipped)]


def find_compiled(plugin: str, addon_path: str) -> Path | None:
    """The newest .vtex_c compiled from `addon_path`; the compiler names it <stem>_png_<hash>."""
    source = PurePosixPath(addon_path)
    folder = game.compiled_addon(plugin) / source.parent
    found = sorted(
        folder.glob(f"{source.stem}_{source.suffix.lstrip('.')}_*.vtex_c"),
        key=lambda p: p.stat().st_mtime,
    )
    return found[-1] if found else None


def check(folder: ModelFolder, addon_path: str, source: Path) -> CompiledReport:
    size = read_image_size(source)
    compiled = find_compiled(folder.plugin, addon_path)
    if compiled is None:
        return CompiledReport(folder.name, addon_path, size, None, problems=["not compiled"])
    texture = vtex.read(compiled)
    report = CompiledReport(folder.name, addon_path, size, (texture.width, texture.height))
    if max(report.shipped) < max(size):
        report.problems.append("downscaled by the compiler")
    elif compiled.stat().st_mtime < source.stat().st_mtime:
        report.problems.append("older than its source")
    return report


def audit(folders: list[ModelFolder]) -> list[CompiledReport]:
    reports, seen = [], set()
    for folder in folders:
        for material in folder.materials:
            for key in SHIPPED_KEYS:
                addon_path = material.keys.get(key, "")
                source = folder.find_texture(addon_path)
                if source is None or addon_path in seen or is_solid_colour(source):
                    continue
                seen.add(addon_path)
                reports.append(check(folder, addon_path, source))
    return reports
