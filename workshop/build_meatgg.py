import os
import shutil
import subprocess
from pathlib import Path

from voltmod.content.content import has_source
from voltmod.panorama.compiler import PANORAMA_DIRS
from voltmod.project import Project
from voltmod.steam import find_client
from voltmod.workshop_tools import AddonDirs

STRONGHOLD_CONTENT = ("models", "materials", "particles", "scripts", "soundevents", "sounds")
SCREENS = ("main-menu", "admin-system", "stronghold")


def main() -> None:
    """Rebuild the meatgg addon: every screen, Stronghold's content and this folder's meatgg/."""
    project = Project.load()
    client = find_client(Path(path) if (path := os.environ.get("CS2_CLIENT_PATH")) else None)
    dirs = AddonDirs.of(client, "meatgg")
    sources, meatgg = dirs.sources, dirs.compiled
    stronghold = AddonDirs.of(client, "stronghold").compiled

    if not stronghold.is_dir():
        raise SystemExit(f"no compiled stronghold addon at {stronghold}")

    # Nothing else deletes from the addon, so a renamed or removed file would keep shipping.
    for addon in (sources, meatgg):
        for folder in PANORAMA_DIRS:
            shutil.rmtree(addon / "panorama" / folder, ignore_errors=True)
    for folder in STRONGHOLD_CONTENT:
        shutil.rmtree(meatgg / folder, ignore_errors=True)

    compile_screens = ["panorama", "compile", *SCREENS, "--addon", "meatgg", "--no-deploy"]
    subprocess.run(["voltmod", *compile_screens], check=True)

    # A compiled file whose source left the repo stays out of the addon.
    content = project.plugin("stronghold").content_dir

    def stale(folder: str, names: list[str]) -> list[str]:
        relative = Path(folder).relative_to(stronghold)
        return [name for name in names if not has_source(content, relative / name)]

    for folder in STRONGHOLD_CONTENT:
        shutil.copytree(stronghold / folder, meatgg / folder, ignore=stale)
    shutil.copytree(Path(__file__).parent / "meatgg", meatgg, dirs_exist_ok=True)

    print(f"Filled {meatgg}. Update the meatgg item in the Workshop Manager.")


if __name__ == "__main__":
    main()
