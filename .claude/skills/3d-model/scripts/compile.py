"""Compile one model or particle folder of a workshop addon, and optionally install it as loose
files.

Usage:
    uv run python .claude/skills/3d-model/scripts/compile.py <addon source> <folder>
        [--addon <name>] [--install client server] [--prune]

    <addon source>  the addon's source tree in the repo, e.g. plugins/stronghold/content
    <folder>        a model's or effect's folder inside it, e.g. models/stronghold/jump_pad

Steps: report source files no .vmdl, .vmat, .vpcf or DMX refers to (--prune deletes them), check
the .vpcf field names against the game's schema (particles.py), mirror the folder into
<client>/content/csgo_addons/<addon>/ (dropping files the source no longer has), wipe its compiled
folder so renamed textures leave nothing behind, compile every .vmdl and .vpcf in it, and with
--install mirror the compiled folder into game/csgo of the client and/or the server.

Paths come from .env: CS2_CLIENT_PATH (default: Steam's usual install) and CS2_SERVER_PATH.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from particles import check

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CLIENT = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
# Sources the addon keeps beside the model but never references from a compiled file.
UNREFERENCED_OK = {".blend", ".vmdl", ".vpcf"}
COMPILED = (".vmdl", ".vpcf")
REFERENCE = re.compile(rb"[\w/.-]+\.(?:dmx|vmat|png|tga|psd|jpg)", re.IGNORECASE)


def referenced(folder: Path) -> set[str]:
    """File names inside `folder` that its .vmdl, .vmat, .vpcf or DMX files name."""
    names: set[str] = set()
    for path in folder.iterdir():
        if path.suffix.lower() in (".vmdl", ".vmat", ".dmx", ".vpcf"):
            for match in REFERENCE.findall(path.read_bytes()):
                names.add(Path(match.decode(errors="ignore")).name.lower())
    return names


def orphans(folder: Path) -> list[Path]:
    names = referenced(folder)
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() not in UNREFERENCED_OK and p.name.lower() not in names
    )


def mirror(source: Path, target: Path, skip: tuple[str, ...] = ()) -> None:
    """Makes `target` hold exactly the files of `source`, minus suffixes in `skip`."""
    if target.exists() and target.resolve() == source.resolve():
        return
    target.mkdir(parents=True, exist_ok=True)
    wanted = {p.name for p in source.iterdir() if p.is_file() and p.suffix.lower() not in skip}
    for stale in target.iterdir():
        if stale.is_file() and stale.name not in wanted:
            stale.unlink()
    for name in wanted:
        shutil.copy2(source / name, target / name)


def compile_folder(client: Path, content: Path) -> bool:
    compiler = client / "game" / "bin" / "win64" / "resourcecompiler.exe"
    ok = True
    for source in sorted(p for p in content.iterdir() if p.suffix.lower() in COMPILED):
        result = subprocess.run(
            [str(compiler), "-i", str(source), "-r"], capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        for line in lines:
            if "ERROR" in line or "WARNING" in line or " compiled, " in line:
                print(f"  {line.strip()}")
        ok = ok and result.returncode == 0 and any(" 0 failed" in line for line in lines)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("folder", type=Path)
    parser.add_argument(
        "--addon", help="the csgo_addons folder name; default: the plugin folder name"
    )
    parser.add_argument("--install", nargs="*", choices=("client", "server"), default=[])
    parser.add_argument("--prune", action="store_true", help="delete unreferenced source files")
    args = parser.parse_args()

    settings = dotenv_values(ROOT / ".env")
    client = Path(settings.get("CS2_CLIENT_PATH") or DEFAULT_CLIENT)
    source_root = (ROOT / args.source).resolve()
    addon = args.addon or (
        source_root.parent.name if source_root.name == "content" else source_root.name
    )
    folder = source_root / args.folder
    if not folder.is_dir():
        raise SystemExit(f"no folder at {folder}")

    for path in orphans(folder):
        if args.prune:
            path.unlink()
            print(f"pruned {path.relative_to(ROOT)}")
        else:
            print(f"unreferenced {path.relative_to(ROOT)} (--prune deletes it)")

    if effects := sorted(folder.glob("*.vpcf")):
        try:
            unknown = check(effects)
        except FileNotFoundError as missing:
            print(f"particle fields not checked: {missing}")
        else:
            for path, where, cls, field in unknown:
                print(f"{path.name}: {where}: {cls} has no field {field}")
            if unknown:
                print("compile stopped: the compiler would drop these fields")
                return 1

    content = client / "content" / "csgo_addons" / addon / args.folder
    compiled = client / "game" / "csgo_addons" / addon / args.folder
    mirror(folder, content, skip=(".blend",))
    shutil.rmtree(compiled, ignore_errors=True)
    print(f"compiling {content}")
    if not compile_folder(client, content):
        print("compile failed")
        return 1

    targets = {"client": str(client), "server": settings.get("CS2_SERVER_PATH") or ""}
    for name in args.install:
        if not targets[name]:
            raise SystemExit(f"CS2_{name.upper()}_PATH is not set in .env")
        game = Path(targets[name]) / "game" / "csgo" / args.folder
        mirror(compiled, game)
        print(f"installed into {game}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
