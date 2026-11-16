"""Raw Cycles bakes into the PNGs a model ships, and marks stamped into textures already
shipped."""

from collections.abc import Iterable
from pathlib import Path

lazy import numpy as np
lazy from PIL import Image

from modelkit.marks import Mark, write_hidden
from modelkit.source2.vmat import BAKED_SUFFIXES

# The value of atlas space no face uses, per channel.
EMPTY = {"color": (0, 0, 0), "normal": (128, 128, 255), "roughness": 255, "metalness": 0}


def read_red(path: str) -> np.ndarray:
    """A grey bake's values, from its red channel."""
    return np.asarray(Image.open(path).convert("RGBA").getchannel("R"))


def to_bytes(values: np.ndarray) -> np.ndarray:
    return np.clip(values * 255 + 0.5, 0, 255).astype(np.uint8)


class TextureSet:
    """One part's baked channels, loaded from the raw RGBA bakes; colour and roughness are
    floats for marking, normal and metalness stay bytes."""

    def __init__(self, raw: dict[str, str]) -> None:
        color = np.asarray(Image.open(raw["color"]).convert("RGBA"), dtype=np.float32) / 255
        self.covered = color[..., 3] > 0
        self.color = color[..., :3]
        self.roughness = read_red(raw["roughness"]).astype(np.float32) / 255
        self.normal = np.asarray(Image.open(raw["normal"]).convert("RGB"))
        self.metalness = read_red(raw["metalness"])

    def stamp(self, marks: Iterable[Mark]) -> None:
        size = self.covered.shape[0]
        for mark in marks:
            mark.press(self.color, self.roughness, mark.draw(size) * self.covered)

    def hide(self, text: str) -> None:
        write_hidden(self.color, self.covered, text)

    def save(self, folder: Path, stem: str) -> dict[str, Path]:
        """Writes <stem>_<suffix>.png per channel into `folder`."""
        folder.mkdir(parents=True, exist_ok=True)
        channels = {
            "color": to_bytes(self.color),
            "normal": self.normal.copy(),
            "roughness": to_bytes(self.roughness),
            "metalness": self.metalness.copy(),
        }
        written = {}
        for channel, pixels in channels.items():
            if channel != "color":
                pixels[~self.covered] = EMPTY[channel]
            written[channel] = folder / f"{stem}_{BAKED_SUFFIXES[channel]}.png"
            Image.fromarray(pixels).save(written[channel])
        return written


def stamp_texture(color_path: Path, rough_path: Path | None, marks: list[Mark]) -> list[Path]:
    """Stamps marks into an existing square colour texture, and for stencils its roughness
    texture too; returns the files changed."""
    image = Image.open(color_path)
    color = np.asarray(image.convert("RGB"), dtype=np.float32) / 255
    size = color.shape[0]
    if color.shape[1] != size:
        raise ValueError(f"{color_path.name} is not square")
    stencil = rough_path is not None and any(mark.style == "stencil" for mark in marks)
    rough_image = Image.open(rough_path) if stencil else None
    rough = (
        np.asarray(rough_image.convert("L").resize((size, size)), dtype=np.float32) / 255
        if rough_image
        else np.zeros((size, size), dtype=np.float32)
    )
    for mark in marks:
        mark.press(color, rough, mark.draw(size))
    Image.fromarray(to_bytes(color)).convert(image.mode).save(color_path)
    if rough_image is None:
        return [color_path]
    resized = Image.fromarray(to_bytes(rough)).resize(rough_image.size)
    resized.convert(rough_image.mode).save(rough_path)
    return [color_path, rough_path]
