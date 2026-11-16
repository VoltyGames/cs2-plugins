"""Maker's marks: text pressed into a texture where a Blender job placed it, and a hidden copy
in atlas space no face uses."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

lazy import numpy as np
lazy from PIL import Image, ImageDraw, ImageFont

FONTS = (r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\arialbd.ttf")
TEXT_PIXELS = 96
STENCIL = (0.82, 0.80, 0.74)
# The hidden mark needs this many clear rows along the atlas's top edge.
HIDDEN_ROWS = 16


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def draw_text(text: str, size: int = TEXT_PIXELS) -> Image.Image:
    """White text on black, cropped to the ink."""
    font = load_font(size)
    left, top, right, bottom = font.getbbox(text)
    image = Image.new("L", (right - left + 8, bottom - top + 8))
    ImageDraw.Draw(image).text((4 - left, 4 - top), text, fill=255, font=font)
    return image


@dataclass(frozen=True)
class Mark:
    """A mark placed in UV space: `uv` its centre, `right` and `up` the UV step for one unit
    along the face."""

    text: str
    uv: tuple[float, float]
    right: tuple[float, float]
    up: tuple[float, float]
    height: float = 1.0
    style: str = "stamp"

    @classmethod
    def from_frame(cls, frame: dict[str, Any]) -> Self:
        return cls(
            frame["text"],
            tuple(frame["uv"]),
            tuple(frame["right"]),
            tuple(frame["up"]),
            frame.get("height", 1.0),
            frame.get("style", "stamp"),
        )

    def draw(self, size: int) -> np.ndarray:
        """The text laid onto a `size` square texture, `height` units tall, as a 0-1 mask."""
        text = draw_text(self.text)
        width_px, height_px = text.size
        unit = self.height / height_px  # units per text pixel
        origin = np.array([self.uv[0] * size, (1 - self.uv[1]) * size])
        right = np.array([self.right[0] * size, -self.right[1] * size])
        up = np.array([self.up[0] * size, -self.up[1] * size])
        # Texture = M @ (text x, text y) + offset, with text y running down.
        m = np.column_stack([unit * right, -unit * up])
        offset = origin - unit * width_px / 2 * right + unit * height_px / 2 * up
        inverse = np.linalg.inv(m)
        shift = -inverse @ offset
        data = (*inverse[0], shift[0], *inverse[1], shift[1])
        placed = text.transform(
            (size, size), Image.Transform.AFFINE, data, Image.Resampling.BILINEAR
        )
        return np.asarray(placed, dtype=np.float32) / 255

    def press(self, color: np.ndarray, rough: np.ndarray, mask: np.ndarray) -> None:
        """Marks `color` and `rough` in place: a stamp presses the paint darker, a stencil
        paints it off-white."""
        weight = mask[..., None]
        if self.style == "stencil":
            color[:] = color * (1 - 0.8 * weight) + np.array(STENCIL) * 0.8 * weight
            rough[:] = rough * (1 - 0.8 * mask) + 0.7 * 0.8 * mask
        else:
            color[:] = color * (1 - 0.5 * weight)


def write_hidden(color: np.ndarray, covered: np.ndarray, text: str) -> None:
    """Writes `text` across the rows no face covers at the top of the atlas."""
    used = np.flatnonzero(covered.any(axis=1))
    band = int(used[0]) if len(used) else covered.shape[0]
    if band < HIDDEN_ROWS:
        raise ValueError("no free band at the top of the atlas for the hidden mark")
    mask = draw_text(text)
    height = int(band * 0.6)
    width = min(int(mask.size[0] * height / mask.size[1]), color.shape[1] - 2 * height)
    tile = np.asarray(mask.resize((width, height)), dtype=np.float32) / 255
    top, left = (band - height) // 2, height
    region = color[top : top + height, left : left + width]
    region[:] = np.maximum(region, tile[..., None] * 0.6)
