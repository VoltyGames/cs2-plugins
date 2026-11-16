"""Raw Cycles bakes into the PNGs a model ships, with the hidden mark."""

from pathlib import Path

lazy import numpy as np
lazy from PIL import Image

from modelkit.marks import write_hidden
from modelkit.source2.vmat import BAKED_SUFFIXES

# The value of atlas space no face uses, per channel.
EMPTY = {"color": (0, 0, 0), "normal": (128, 128, 255), "roughness": 255, "metalness": 0}


def read_red(path: str) -> np.ndarray:
    """A grey bake's values, from its red channel."""
    return np.asarray(Image.open(path).convert("RGBA").getchannel("R"))


def to_bytes(values: np.ndarray) -> np.ndarray:
    return np.clip(values * 255 + 0.5, 0, 255).astype(np.uint8)


class TextureSet:
    """One part's baked channels, loaded from the raw RGBA bakes; colour and roughness as
    floats, normal and metalness as bytes."""

    def __init__(self, raw: dict[str, str]) -> None:
        color = np.asarray(Image.open(raw["color"]).convert("RGBA"), dtype=np.float32) / 255
        self.covered = color[..., 3] > 0
        self.color = color[..., :3]
        self.roughness = read_red(raw["roughness"]).astype(np.float32) / 255
        self.normal = np.asarray(Image.open(raw["normal"]).convert("RGB"))
        self.metalness = read_red(raw["metalness"])

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
