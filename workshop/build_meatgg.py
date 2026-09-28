import os
import shutil
import subprocess
from pathlib import Path

from deploy.bundle.server_assets import has_source

DEFAULT_CLIENT = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
STRONGHOLD_CONTENT = ("models", "materials", "particles", "scripts", "soundevents", "sounds")
PANORAMA_OUTPUT = ("layout/custom_game", "styles/custom_game", "images/custom_game")
SCREENS = ("main-menu", "admin-system", "stronghold")


def main() -> None:
    """Rebuild the meatgg addon: every screen, Stronghold's content and this folder's meatgg/."""
    client = Path(os.environ.get("CS2_CLIENT_PATH", DEFAULT_CLIENT))
    sources = client / "content" / "csgo_addons" / "meatgg"
    meatgg = client / "game" / "csgo_addons" / "meatgg"
    stronghold = client / "game" / "csgo_addons" / "stronghold"

    if not stronghold.is_dir():
        raise SystemExit(f"no compiled stronghold addon at {stronghold}")

    # Nothing else deletes from the addon, so a renamed or removed file would keep shipping.
    for addon in (sources, meatgg):
        for folder in PANORAMA_OUTPUT:
            shutil.rmtree(addon / "panorama" / folder, ignore_errors=True)
    for folder in STRONGHOLD_CONTENT:
        shutil.rmtree(meatgg / folder, ignore_errors=True)

    compile_screens = ["panorama", "compile", *SCREENS, "--addon", "meatgg", "--no-deploy"]
    subprocess.run(["voltmod", *compile_screens], check=True)

    # A compiled file whose source left the repo stays out of the addon.
    content = Path(__file__).parents[1] / "plugins" / "stronghold" / "content"
    for folder in STRONGHOLD_CONTENT:
        for file in (stronghold / folder).rglob("*"):
            relative = file.relative_to(stronghold)
            if file.is_file() and has_source(content, relative):
                (meatgg / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, meatgg / relative)
    shutil.copytree(Path(__file__).parent / "meatgg", meatgg, dirs_exist_ok=True)

    print(f"Filled {meatgg}. Update the meatgg item in the Workshop Manager.")


if __name__ == "__main__":
    main()
