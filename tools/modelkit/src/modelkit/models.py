"""A plugin's model folders and the materials in them."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePosixPath

lazy from PIL import Image

from modelkit import game
from modelkit.source2 import vmat, vmdl

# Textures this small are flat colours, such as glow and team colours; audits skip them.
SOLID_COLOUR = 64


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def is_solid_colour(path: Path) -> bool:
    return max(read_image_size(path)) <= SOLID_COLOUR


class ModelFolder:
    """content/models/<plugin>/<model>/: the model's .blend, DMX, materials and textures."""

    def __init__(self, plugin: str, path: Path) -> None:
        self.plugin = plugin
        self.path = path
        self.name = path.name
        self.blend = path / f"{self.name}.blend"
        self.addon_path = f"models/{plugin}/{self.name}/"

    @classmethod
    def find_all(cls, plugin: str, only: list[str] | None = None) -> list[ModelFolder]:
        """The plugin's model folders, or just those named in `only`."""
        root = game.models_dir(plugin)
        if not root.is_dir():
            raise FileNotFoundError(f"no models at {root}")
        folders = sorted(p for p in root.iterdir() if p.is_dir())
        if only:
            missing = set(only) - {p.name for p in folders}
            if missing:
                raise FileNotFoundError(f"no model folder {', '.join(sorted(missing))} in {root}")
            folders = [p for p in folders if p.name in only]
        return [cls(plugin, path) for path in folders]

    @classmethod
    def find(cls, plugin: str, model: str) -> ModelFolder:
        [folder] = cls.find_all(plugin, [model])
        return folder

    def find_texture(self, addon_path: str) -> Path | None:
        """The source file behind an addon path such as "models/x/x_color.png", if present."""
        path = game.plugin_dir(self.plugin) / "content" / addon_path
        return path if addon_path and path.is_file() else None

    def read_scales(self) -> dict[str, float]:
        """Each render mesh DMX stem's model scale, from the folder's .vmdl files."""
        scales = {}
        for path in self.path.glob("*.vmdl"):
            model = vmdl.read_vmdl(path)
            scales |= {PurePosixPath(mesh).stem: model.scale for mesh in model.meshes}
        return scales

    @cached_property
    def materials(self) -> list[Material]:
        swapped = {
            PurePosixPath(swapped).name
            for model in self.path.glob("*.vmdl")
            for swapped in vmdl.read_vmdl(model).swapped
        }
        return [
            Material(self, path.name, vmat.read_vmat(path), path.name in swapped)
            for path in sorted(self.path.glob("*.vmat"))
        ]

    def read_texture_names(self, material: str) -> set[str]:
        """The file names of the textures a .vmat in this folder names."""
        return {Path(value).name for value in vmat.read_vmat(self.path / material).values()}


@dataclass(frozen=True)
class Material:
    folder: ModelFolder
    name: str
    keys: dict[str, str]
    swapped: bool
    """A material group remaps it, as for team colours."""

    @property
    def accent(self) -> bool:
        """A team colour or glow, flat on purpose."""
        return self.swapped or self.keys.get("F_SELF_ILLUM") == "1"

    @property
    def baked(self) -> bool:
        """A baked texture set, which ships no AO map on purpose."""
        return self.keys.get("F_METALNESS_TEXTURE") == "1"

    def find_texture(self, key: str) -> Path | None:
        """The source file of a texture key such as "TextureColor"."""
        return self.folder.find_texture(self.keys.get(key, ""))

    def find_detailed_texture(self, key: str) -> Path | None:
        """The texture of `key` unless it is missing or a solid colour."""
        path = self.find_texture(key)
        return path if path and not is_solid_colour(path) else None
