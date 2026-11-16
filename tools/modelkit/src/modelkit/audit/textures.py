"""Why a model looks flat: colour contrast, roughness, normal strength, AO and metalness."""

from dataclasses import dataclass
from pathlib import Path

lazy import numpy as np
lazy from PIL import Image

from modelkit.audit import Report, format_number, format_size
from modelkit.models import Material, ModelFolder, read_image_size

# Thresholds on 0-255 values, from the Stronghold models that read as flat in game.
FLAT_CONTRAST = 8.0
WEAK_NORMAL = 8.0
# Atlas pixels darker than this are unmapped space, left out of the statistics.
UNMAPPED = 6
SAMPLE = 512


@dataclass
class TextureReport(Report):
    COLUMNS = ("model", "material", "size", "contrast", "roughness", "normal", "AO", "metal")
    model: str
    material: str
    size: tuple[int, int]
    contrast: float
    roughness: str
    normal: float | None
    ambient_occlusion: str
    metalness: str

    def cells(self) -> list[str]:
        return [
            self.model,
            self.material,
            format_size(self.size),
            f"{self.contrast:.1f}",
            self.roughness,
            format_number(self.normal, ".1f"),
            self.ambient_occlusion,
            self.metalness,
        ]


def load(path: Path, mode: str) -> np.ndarray:
    image = Image.open(path)
    image.draft(mode, (SAMPLE, SAMPLE))
    image = image.convert(mode)
    image.thumbnail((SAMPLE, SAMPLE))
    return np.asarray(image, dtype=np.float32)


def resize_mask(mask: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    if mask.shape == shape[:2]:
        return mask
    image = Image.fromarray(mask.astype(np.uint8) * 255).resize((shape[1], shape[0]))
    return np.asarray(image) > 127


def check(material: Material) -> TextureReport | None:
    """None for a material meant to be flat: a team colour, a glow or a solid colour."""
    color = material.find_detailed_texture("TextureColor")
    if material.accent or color is None:
        return None
    luminance = load(color, "L")
    mapped = luminance > UNMAPPED
    contrast = float(luminance[mapped].std()) if mapped.any() else 0.0

    roughness = "constant"
    if rough := material.find_detailed_texture("TextureRoughness"):
        values = load(rough, "L")
        values = values[resize_mask(mapped, values.shape)]
        roughness = f"{values.mean():.0f} ± {values.std():.0f}"

    normal = None
    if normal_path := material.find_texture("TextureNormal"):
        pixels = load(normal_path, "RGB")
        inside = resize_mask(mapped, pixels.shape)
        normal = float((pixels[..., 0][inside].std() + pixels[..., 1][inside].std()) / 2)

    occlusion = material.find_texture("TextureAmbientOcclusion") is not None
    metal_map = material.baked
    report = TextureReport(
        model=material.folder.name,
        material=material.name,
        size=read_image_size(color),
        contrast=contrast,
        roughness=roughness,
        normal=normal,
        ambient_occlusion="baked" if occlusion else "default",
        metalness="map" if metal_map else f"{float(material.keys.get('g_flMetalness', 0)):g}",
    )
    if contrast < FLAT_CONTRAST:
        report.problems.append("flat colour")
    if roughness == "constant":
        report.problems.append("one roughness")
    if normal is None:
        report.problems.append("no normal map")
    elif normal < WEAK_NORMAL:
        report.problems.append("weak normals")
    if not occlusion and not material.baked:
        report.problems.append("no AO")
    return report


def audit(folders: list[ModelFolder]) -> list[TextureReport]:
    reports = (check(m) for folder in folders for m in folder.materials)
    return [r for r in reports if r is not None]
