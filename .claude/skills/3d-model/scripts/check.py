"""Check the tools a model task needs outside Blender, before starting one.

Usage: uv run python .claude/skills/3d-model/scripts/check.py [<plugin>]

Checks Codex and its imagegen skill, Git LFS, the CS2 Workshop Tools compiler, the server path,
and whether CS2 is running. With a plugin name, also its addon source, the addon's content
folder under the Workshop Tools, and the LFS rules for the addon's art. Blender itself is checked
from inside Blender: modelkit.session.status().
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CLIENT = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
LFS_ART = ("png", "dmx", "blend")


def report(ok: bool, what: str, detail: str = "") -> bool:
    print(f"{'ok     ' if ok else 'MISSING'} {what}{f': {detail}' if detail else ''}")
    return ok


def running_cs2() -> list[str]:
    tasks = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq cs2.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
    )
    return [
        line.split(",")[1].strip('"') for line in tasks.stdout.splitlines() if "cs2.exe" in line
    ]


def lfs_rules(plugin: Path) -> list[str]:
    attributes = plugin / ".gitattributes"
    text = attributes.read_text() if attributes.exists() else ""
    return [ext for ext in LFS_ART if f"content/**/*.{ext} filter=lfs" not in text]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("plugin", nargs="?", help="plugin folder name, e.g. stronghold")
    args = parser.parse_args()

    settings = dotenv_values(ROOT / ".env")
    client = Path(settings.get("CS2_CLIENT_PATH") or DEFAULT_CLIENT)
    server = settings.get("CS2_SERVER_PATH") or ""
    imagegen = [Path.home() / ".codex" / "skills" / p / "imagegen" for p in (".system", "")]
    compiler = client / "game" / "bin" / "win64" / "resourcecompiler.exe"

    ok = report(bool(shutil.which("codex")), "codex CLI")
    ok &= report(any(p.is_dir() for p in imagegen), "codex imagegen skill")
    lfs = subprocess.run(["git", "lfs", "version"], capture_output=True, text=True)
    ok &= report(lfs.returncode == 0, "git lfs")
    ok &= report(compiler.exists(), "resourcecompiler", str(compiler))
    report(bool(server) and Path(server).is_dir(), "CS2_SERVER_PATH", server or "not set in .env")
    if pids := running_cs2():
        report(False, "CS2 stopped", f"cs2.exe running (pid {', '.join(pids)}); installs will fail")

    if args.plugin:
        plugin = ROOT / "plugins" / args.plugin
        source = plugin / "content"
        content = client / "content" / "csgo_addons" / args.plugin
        ok &= report(source.is_dir(), "addon source", str(source.relative_to(ROOT)))
        kind = "junction" if content.is_junction() else "copy; content compile mirrors into it"
        ok &= report(content.is_dir(), "addon content folder", f"{content} ({kind})")
        missing = lfs_rules(plugin)
        report(
            not missing, "LFS rules", f"add content/**/*.{{{','.join(missing)}}}" if missing else ""
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
