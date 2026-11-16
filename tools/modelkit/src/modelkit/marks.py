"""The hidden maker's mark: text in the band of a baked atlas that no face uses."""

from pathlib import Path

lazy import numpy as np
lazy from PIL import Image, ImageDraw, ImageFont

FONTS = (r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\arialbd.ttf")
TEXT_PIXELS = 96
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
