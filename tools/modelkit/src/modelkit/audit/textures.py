"""Why a model looks flat: colour contrast, roughness, normal strength, AO and metalness."""

from dataclasses import dataclass, field
from pathlib import Path

lazy import numpy as np
lazy from PIL import Image

from modelkit.audit import SOLID_COLOUR, Material, find_source, read_materials, read_png_size

# Thresholds on 0-255 values, from the Stronghold models that read as flat in game.
FLAT_CONTRAST = 8.0
WEAK_NORMAL = 8.0
# Atlas pixels darker than this are unmapped space, left out of the statistics.
UNMAPPED = 6
SAMPLE = 512


@dataclass
class TextureReport:
    model: str
    material: str
    size: tuple[int, int]
    contrast: float
    roughness: str
    normal: float | None
    ambient_occlusion: str
    metalness: str
    problems: list[str] = field(default_factory=list)


def load(path: Path, mode: str) -> np.ndarray:
    image = Image.open(path)
    image.draft(mode, (SAMPLE, SAMPLE))
    image = image.convert(mode)
    image.thumbnail((SAMPLE, SAMPLE))
    return np.asarray(image, dtype=np.float32)


def resized(mask: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    if mask.shape == shape[:2]:
        return mask
    image = Image.fromarray(mask.astype(np.uint8) * 255).resize((shape[1], shape[0]))
    return np.asarray(image) > 127


def check(plugin: str, material: Material) -> TextureReport | None:
    """None for a material meant to be flat: a team colour, a glow or a solid colour."""
    if material.accent:
        return None
    color = find_source(plugin, material.keys.get("TextureColor", ""))
    if color is None or max(read_png_size(color)) <= SOLID_COLOUR:
        return None
    luminance = load(color, "L")
    mapped = luminance > UNMAPPED
    contrast = float(luminance[mapped].std()) if mapped.any() else 0.0

    rough = find_source(plugin, material.keys.get("TextureRoughness", ""))
    if rough is None or max(read_png_size(rough)) <= SOLID_COLOUR:
        roughness = "constant"
    else:
        values = load(rough, "L")
        values = values[resized(mapped, values.shape)]
        roughness = f"{values.mean():.0f} ± {values.std():.0f}"

    normal_path = find_source(plugin, material.keys.get("TextureNormal", ""))
    normal = None
    if normal_path is not None:
        pixels = load(normal_path, "RGB")
        inside = resized(mapped, pixels.shape)
        normal = float((pixels[..., 0][inside].std() + pixels[..., 1][inside].std()) / 2)

    baked = find_source(plugin, material.keys.get("TextureAmbientOcclusion", "")) is not None
    metal_map = material.keys.get("F_METALNESS_TEXTURE") == "1"
    report = TextureReport(
        model=material.model,
        material=material.name,
        size=read_png_size(color),
        contrast=contrast,
        roughness=roughness,
        normal=normal,
        ambient_occlusion="baked" if baked else "default",
        metalness="map" if metal_map else f"{float(material.keys.get('g_flMetalness', 0)):g}",
    )
    if contrast < FLAT_CONTRAST:
        report.problems.append("flat colour")
    if roughness == "constant":
        report.problems.append("one roughness")
    if normal is None or normal < WEAK_NORMAL:
        report.problems.append("weak normals" if normal is not None else "no normal map")
    if not baked:
        report.problems.append("no AO")
    return report


def audit(plugin: str, folders: list[Path]) -> list[TextureReport]:
    reports = (check(plugin, m) for folder in folders for m in read_materials(folder))
    return [r for r in reports if r is not None]
