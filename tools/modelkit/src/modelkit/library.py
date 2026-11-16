"""CC0 tiling materials from Poly Haven and ambientCG, downloaded on first use into build/.

A bake recipe names one as "polyhaven:<id>" or "ambientcg:<id>"; the repository keeps only the
name, so the source art stays out of Git.
"""

import io
import json
import urllib.request
import zipfile
from pathlib import Path

from modelkit import game

CACHE = game.REPO / "build" / "materials"
RESOLUTION = "2k"
MAPS = ("color", "normal", "roughness", "metalness", "ao")
# Each source's name for our maps.
POLYHAVEN = {
    "color": "Diffuse",
    "normal": "nor_gl",
    "roughness": "Rough",
    "metalness": "Metal",
    "ao": "AO",
}
AMBIENTCG = {
    "color": "Color",
    "normal": "NormalGL",
    "roughness": "Roughness",
    "metalness": "Metalness",
    "ao": "AmbientOcclusion",
}
AGENT = {"User-Agent": "modelkit"}


def download(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as reply:
        return reply.read()


def fetch_polyhaven(asset: str, folder: Path) -> None:
    files = json.loads(download(f"https://api.polyhaven.com/files/{asset}"))
    for name, key in POLYHAVEN.items():
        if key in files:
            url = files[key][RESOLUTION]["png"]["url"]
            (folder / f"{name}.png").write_bytes(download(url))


def fetch_ambientcg(asset: str, folder: Path) -> None:
    archive = zipfile.ZipFile(
        io.BytesIO(download(f"https://ambientcg.com/get?file={asset}_2K-PNG.zip"))
    )
    for name, key in AMBIENTCG.items():
        member = next((m for m in archive.namelist() if m.endswith(f"_{key}.png")), None)
        if member:
            (folder / f"{name}.png").write_bytes(archive.read(member))


def find_maps(reference: str) -> dict[str, str]:
    """The material's map files by role ("color", "normal", ...), downloading them if needed."""
    source, _, asset = reference.partition(":")
    fetchers = {"polyhaven": fetch_polyhaven, "ambientcg": fetch_ambientcg}
    if source not in fetchers or not asset:
        raise ValueError(f"{reference}: name a material as polyhaven:<id> or ambientcg:<id>")
    folder = CACHE / source / asset
    if not (folder / "color.png").exists():
        folder.mkdir(parents=True, exist_ok=True)
        fetchers[source](asset, folder)
    return {name: str(folder / f"{name}.png") for name in MAPS if (folder / f"{name}.png").exists()}
