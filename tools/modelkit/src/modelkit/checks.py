"""The tools a model task needs, checked before starting one."""

import shutil
import subprocess
from pathlib import Path

from modelkit import console, game, headless

LFS_ART = ("png", "dmx", "blend")


def find_missing_lfs_rules(plugin: Path) -> list[str]:
    attributes = plugin / ".gitattributes"
    text = attributes.read_text() if attributes.exists() else ""
    return [ext for ext in LFS_ART if f"content/**/*.{ext} filter=lfs" not in text]


def check_blender() -> bool:
    blender = game.find_blender()
    if not console.check(blender is not None, "Blender", str(blender or "set BLENDER_PATH")):
        return False
    try:
        status = headless.run_job("status", user_settings=True)
    except headless.BlenderError as failed:
        return console.check(False, "Blender runs", str(failed))
    console.info(f"        Blender {status['blender']}")
    version = ".".join(map(str, status["source_tools"] or ())) or "not installed"
    return console.check(status["source_tools_enabled"], "Blender Source Tools", version)


def run(plugin: str | None) -> bool:
    """Prints a line per tool; False when one a model task needs is missing."""
    imagegen = [Path.home() / ".codex" / "skills" / p / "imagegen" for p in (".system", "")]
    ok = check_blender()
    ok &= console.check(bool(shutil.which("codex")), "codex CLI")
    ok &= console.check(any(p.is_dir() for p in imagegen), "codex imagegen skill")
    lfs = subprocess.run(["git", "lfs", "version"], capture_output=True, text=True)
    ok &= console.check(lfs.returncode == 0, "git lfs")
    ok &= console.check(game.compiler().exists(), "resourcecompiler", str(game.compiler()))
    server = game.settings().get("CS2_SERVER_PATH", "")
    console.check(bool(server) and Path(server).is_dir(), "CS2_SERVER_PATH", server or "not set")
    cap = game.read_texture_cap()
    console.info(f"        texture cap: {cap or 'none'} (PublicToolsDefaultMaxRes)")
    if pids := game.find_running_cs2():
        console.check(False, "CS2 stopped", f"cs2.exe running ({', '.join(pids)}); installs fail")

    if plugin:
        ok &= check_addon(plugin)
    return ok


def check_addon(plugin: str) -> bool:
    folder = game.plugin_dir(plugin)
    source = folder / "content"
    content = game.client() / "content" / "csgo_addons" / plugin
    ok = console.check(source.is_dir(), "addon source", str(source.relative_to(game.REPO)))
    kind = "junction" if content.is_junction() else "copy; content compile mirrors into it"
    ok &= console.check(content.is_dir(), "addon content folder", f"{content} ({kind})")
    missing = find_missing_lfs_rules(folder)
    detail = f"add content/**/*.{{{','.join(missing)}}}" if missing else ""
    console.check(not missing, "LFS rules", detail)
    return ok
