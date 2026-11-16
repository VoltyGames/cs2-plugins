"""Raw bakes into the PNGs a model ships, with its maker's marks: a stamp on the model itself
and a hidden copy in atlas space no face uses."""

from pathlib import Path
from typing import Any

lazy import numpy as np
lazy from PIL import Image, ImageDraw, ImageFont

FONTS = (r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\arialbd.ttf")
# Bake channel: the file suffix it ships as, and the value of atlas space no face uses.
SHIPPED = {
    "color": ("color", (0, 0, 0)),
    "normal": ("normal", (128, 128, 255)),
    "roughness": ("rough", 255),
    "metalness": ("metal", 0),
    "ao": ("ao", 255),
}
STENCIL = (0.82, 0.80, 0.74)
TEXT_PIXELS = 96


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def text_mask(text: str, size: int = TEXT_PIXELS) -> Image.Image:
    """White text on black, cropped to the ink."""
    font = load_font(size)
    left, top, right, bottom = font.getbbox(text)
    image = Image.new("L", (right - left + 8, bottom - top + 8))
    ImageDraw.Draw(image).text((4 - left, 4 - top), text, fill=255, font=font)
    return image


def place(text: Image.Image, frame: dict[str, Any], height: float, size: int) -> np.ndarray:
    """The text laid onto the atlas at `frame`, `height` units tall, as a 0-1 mask."""
    width_px, height_px = text.size
    unit = height / height_px  # units per text pixel
    u, v = frame["uv"]
    origin = np.array([u * size, (1 - v) * size])
    right = np.array([frame["right"][0] * size, -frame["right"][1] * size])
    up = np.array([frame["up"][0] * size, -frame["up"][1] * size])
    # Atlas = M @ (text x, text y) + offset, with text y running down.
    m = np.column_stack([unit * right, -unit * up])
    offset = origin - unit * width_px / 2 * right + unit * height_px / 2 * up
    inverse = np.linalg.inv(m)
    shift = -inverse @ offset
    data = (*inverse[0], shift[0], *inverse[1], shift[1])
    placed = text.transform((size, size), Image.Transform.AFFINE, data, Image.Resampling.BILINEAR)
    return np.asarray(placed, dtype=np.float32) / 255


def find_free_band(covered: np.ndarray) -> int:
    """How many rows at the top of the atlas no face covers."""
    used = np.flatnonzero(covered.any(axis=1))
    return int(used[0]) if len(used) else covered.shape[0]


def write_hidden(color: np.ndarray, covered: np.ndarray, text: str) -> bool:
    """Writes `text` across the free band at the top of the atlas; False when there is none."""
    band = find_free_band(covered)
    if band < 16:
        return False
    mask = text_mask(text)
    height = int(band * 0.6)
    width = min(int(mask.size[0] * height / mask.size[1]), color.shape[1] - 2 * height)
    tile = np.asarray(mask.resize((width, height)), dtype=np.float32) / 255
    top, left = (band - height) // 2, height
    region = color[top : top + height, left : left + width]
    region[:] = np.maximum(region, tile[..., None] * 0.6)
    return True


def stamp(color: np.ndarray, rough: np.ndarray, mask: np.ndarray, style: str) -> None:
    """Marks `color` and `rough` in place: "stamp" presses the paint darker, "stencil" paints it
    off-white."""
    weight = mask[..., None]
    if style == "stencil":
        color[:] = color * (1 - 0.8 * weight) + np.array(STENCIL) * 0.8 * weight
        rough[:] = rough * (1 - 0.8 * mask) + 0.7 * 0.8 * mask
    else:
        color[:] = color * (1 - 0.5 * weight)


def finish(
    raw: dict[str, str],
    out: Path,
    stem: str,
    frames: list[dict[str, Any]],
    hidden: str | None,
) -> dict[str, Path]:
    """Writes `out`/<stem>_<suffix>.png for each baked channel, marks included."""
    layers = {
        channel: np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
        for channel, path in raw.items()
    }
    covered = layers["color"][..., 3] > 0
    size = covered.shape[0]
    color = layers["color"][..., :3]
    rough = layers["roughness"][..., 0]
    for frame in frames:
        mask = place(text_mask(frame["text"]), frame, frame.get("height", 1.0), size) * covered
        stamp(color, rough, mask, frame.get("style", "stamp"))
    if hidden and not write_hidden(color, covered, hidden):
        raise ValueError("no free band at the top of the atlas for the hidden mark")

    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for channel, (suffix, empty) in SHIPPED.items():
        values = {"color": color, "roughness": rough}.get(channel, layers[channel][..., :3])
        pixels = np.clip(values * 255 + 0.5, 0, 255).astype(np.uint8)
        if pixels.ndim == 3 and channel != "color" and channel != "normal":
            pixels = pixels[..., 0]
        if channel != "color":
            pixels[~covered] = empty
        path = out / f"{stem}_{suffix}.png"
        Image.fromarray(pixels).save(path)
        written[channel] = path
    return written
