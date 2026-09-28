import shutil
from pathlib import Path

from deploy.errors import DeployError
from deploy.paths import ROOT


def has_source(content: Path, compiled: Path) -> bool:
    """Whether `compiled` (relative, e.g. models/x/x.vmdl_c) still has its source in `content`.

    Only resource types compiled one to one are checked; textures and sounds pass.
    """
    if compiled.suffix not in ServerAssets.KEEP + (".vmat_c",):
        return True
    return (content / compiled.with_suffix(compiled.suffix.removesuffix("_c"))).is_file()


class ServerAssets:
    """The compiled workshop files a plugin's server code needs, in plugins/<name>/server-assets.

    The folder installs with the plugin, and the VoltMod host mounts it ahead of the game's VPKs.
    Textures, materials and sound files only render or play on clients, which download the whole
    addon.
    """

    DIR = "server-assets"
    # Models hold collision, hitboxes and attachments; particles and sound events spawn by name;
    # vdata overrides entity subclasses, such as the launchers' weapons.
    KEEP = (".vmdl_c", ".vpcf_c", ".vsndevts_c", ".vdata_c")

    @classmethod
    def folder(cls, plugin: str) -> Path:
        return ROOT / "plugins" / plugin / cls.DIR

    @classmethod
    def export(cls, plugin: str, addon: Path) -> int:
        """Replace the plugin's server-assets with the files it needs from compiled `addon`.

        A compiled file whose source is gone from the plugin's `content/` is left out, so a
        stale compile never ships.
        """
        if not addon.is_dir():
            raise DeployError(f"no compiled addon at {addon}; compile it in the Workshop Tools")
        content = ROOT / "plugins" / plugin / "content"
        destination = cls.folder(plugin)
        shutil.rmtree(destination, ignore_errors=True)
        count = 0
        for file in sorted(addon.rglob("*")):
            relative = file.relative_to(addon)
            # Tool caches such as _bakeresourcecache hold compiled copies too.
            wanted = file.is_file() and file.suffix in cls.KEEP
            if not wanted or relative.parts[0].startswith("_") or not has_source(content, relative):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            count += 1
        return count
