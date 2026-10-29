"""Compare the CS2 client's game files with the copies and derived content this repo keeps."""

import argparse
import difflib
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import vpk

REPO = Path(__file__).resolve().parents[4]
BASELINE = Path(__file__).with_name("baseline.json")
WORKSHOP_GAMEINFO = REPO / "workshop" / "gameinfo.gi"
PANEL_GAMEINFO = REPO / "deploy" / "files" / "panel" / "gameinfo.gi"
OUR_WEAPONS = REPO / "plugins" / "stronghold" / "content" / "scripts" / "weapons.vdata"
STEAM_COMMON = Path("C:/Program Files (x86)/Steam/steamapps/common")
DEFAULT_CLIENT = STEAM_COMMON / "Counter-Strike Global Offensive"

ANCHOR = '\t\t\t"include"       "panorama/images/custom_game"\n'
INCLUDE = '\t\t\t"include"       "panorama/images/icons/skillgroups"\n'
PANEL_NOTE = re.compile(r"^\t// Valve's csgo/gameinfo\.gi.*\n", re.MULTILINE)
STRONGHOLD_ENTRY = re.compile(r"^\t(stronghold_\w+) = \n\t\{\n.*?^\t\}\n", re.MULTILINE | re.DOTALL)


def read_lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def print_diff(old: str, new: str, old_name: str, new_name: str) -> None:
    diff = difflib.unified_diff(old.splitlines(True), new.splitlines(True), old_name, new_name, n=2)
    sys.stdout.writelines(diff)


def client_build(client: Path) -> str:
    steam_inf = (client / "game" / "csgo" / "steam.inf").read_text()
    return re.search(r"ClientVersion=(\d+)", steam_inf).group(1)


def add_include(gameinfo: Path) -> None:
    """Insert the skillgroups include in place, keeping the file's line endings and no BOM."""
    raw = gameinfo.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    anchor = ANCHOR.encode().replace(b"\n", newline)
    line = INCLUDE.encode().replace(b"\n", newline)
    if raw.count(anchor) != 1:
        sys.exit(f"anchor line not found exactly once in {gameinfo}; edit it by hand")
    backup = Path(tempfile.gettempdir()) / "gameinfo.gi.bak"
    shutil.copyfile(gameinfo, backup)
    gameinfo.write_bytes(raw.replace(anchor, anchor + line))
    print(f"added the skillgroups include; backup at {backup}")


def check_gameinfo(client: Path, fix: bool) -> bool:
    gameinfo = client / "game" / "csgo" / "gameinfo.gi"
    stock = read_lf(gameinfo).replace(INCLUDE, "")
    current = True
    if INCLUDE not in read_lf(gameinfo):
        current = False
        print("gameinfo.gi: the skillgroups include is missing")
        if fix:
            add_include(gameinfo)
    copies = {
        "workshop/gameinfo.gi": read_lf(WORKSHOP_GAMEINFO).replace(INCLUDE, ""),
        "deploy/files/panel/gameinfo.gi": PANEL_NOTE.sub("", read_lf(PANEL_GAMEINFO)),
    }
    for name, copy in copies.items():
        if copy == stock:
            print(f"{name}: current")
            continue
        current = False
        print(f"{name}: the game changed gameinfo.gi")
        print_diff(copy, stock, name, "client gameinfo.gi")
    return current


def hash_sources(client: Path, paths: list[str]) -> dict[str, str]:
    pak = vpk.open(str(client / "game" / "csgo" / "pak01_dir.vpk"))
    return {path: hashlib.sha1(pak.get_file(path).read()).hexdigest() for path in paths}


def check_sources(client: Path, record: bool) -> bool:
    baseline = json.loads(BASELINE.read_text())
    files = baseline["files"]
    hashes = hash_sources(client, list(files))
    changed = [path for path in files if hashes[path] != files[path]["sha1"]]
    build = client_build(client)
    for path in changed:
        print(f"{path}: changed since build {baseline['build']}; check {files[path]['feeds']}")
    if not changed:
        print(f"game sources: unchanged since build {baseline['build']} (client {build})")
    if record:
        for path in files:
            files[path]["sha1"] = hashes[path]
        baseline["build"] = build
        BASELINE.write_text(json.dumps(baseline, indent=2) + "\n", newline="\n")
        print(f"recorded build {build} in {BASELINE.relative_to(REPO)}")
    return not changed


def check_weapons(stock_path: Path, write: bool) -> bool:
    stock = read_lf(stock_path)
    ours = read_lf(OUR_WEAPONS)
    entries = [match.group(0) for match in STRONGHOLD_ENTRY.finditer(ours)]
    names = ", ".join(match.group(1) for match in STRONGHOLD_ENTRY.finditer(ours))
    if stock == STRONGHOLD_ENTRY.sub("", ours):
        print(f"weapons.vdata: current (stock plus {names})")
        return True
    print("weapons.vdata: the game changed it")
    print_diff(STRONGHOLD_ENTRY.sub("", ours), stock, "ours without stronghold entries", "stock")
    if write:
        body, closing = stock.rstrip("\n").rsplit("\n", 1)
        merged = body + "\n" + "".join(entries) + closing + "\n"
        OUR_WEAPONS.write_bytes(merged.encode("utf-8"))
        print(f"wrote stock plus {names} to {OUR_WEAPONS.relative_to(REPO)}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, default=DEFAULT_CLIENT, help="CS2 client folder")
    parser.add_argument(
        "--stock-weapons", type=Path, help="weapons.vdata decompiled from the client's VPK"
    )
    parser.add_argument(
        "--add-include", action="store_true", help="add the missing include to the client gameinfo"
    )
    parser.add_argument(
        "--write-weapons", action="store_true", help="rebuild ours from stock plus our entries"
    )
    parser.add_argument(
        "--record", action="store_true", help="save the client's source hashes as the new baseline"
    )
    args = parser.parse_args()
    current = check_gameinfo(args.client, args.add_include)
    current = check_sources(args.client, args.record) and current
    if args.stock_weapons:
        current = check_weapons(args.stock_weapons, args.write_weapons) and current
    sys.exit(0 if current else 1)


if __name__ == "__main__":
    main()
