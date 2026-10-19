"""Run RCON commands against the local dev server, starting it first when asked.

Usage: uv run python .claude/skills/rcon-debug/scripts/local.py [--start] "<command>" ...

Settings come from .env. --start launches cs2.exe detached with -condebug, so the console lands in
console.log under the first `Game` path of gameinfo.gi, and waits until RCON answers.
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402
lazy from voltmod.server.cs2_server import Cs2Server  # noqa: E402

from deploy.rcon import RconClient  # noqa: E402

BOOT_TIMEOUT = 180


def listening_address(port: int) -> str | None:
    """CS2 binds one adapter, often a virtual one, rather than loopback."""
    netstat = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True)
    match = re.search(rf"TCP\s+([\d.]+):{port}\s+\S+\s+LISTENING", netstat.stdout)
    if match is None:
        return None
    return "127.0.0.1" if match.group(1) == "0.0.0.0" else match.group(1)


def start(settings: dict[str, str | None], port: int) -> str:
    server = Cs2Server.open(Path(settings["CS2_SERVER_PATH"] or ""))
    server.restore_voltmod_search_path()
    if server.executable is None:
        raise SystemExit(f"no cs2.exe under {server.root}")
    # fmt: off
    command = [
        server.executable, "-dedicated", "-console", "-usercon", "-condebug",
        "+map", settings.get("CS2_MAP") or "de_dust2", "-port", str(port),
        "-maxplayers", settings.get("CS2_MAX_PLAYERS") or "16", "+game_mode", "0",
        "+rcon_password", settings["RCON_PASSWORD"] or "",
    ]
    # fmt: on
    detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(command, cwd=server.executable.parent, creationflags=detached)
    # The engine writes the log under the first Game path, which is Metamod's when it is installed.
    gameinfo = (server.game_dir / "gameinfo.gi").read_text(errors="replace")
    log_dir = "metamod" if "csgo/addons/metamod" in gameinfo else "voltmod"
    print(f"started; log: {server.game_dir / 'addons' / log_dir / 'console.log'}", flush=True)
    deadline = time.monotonic() + BOOT_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(3)
        if address := listening_address(port):
            return address
    raise SystemExit(f"RCON did not come up within {BOOT_TIMEOUT}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="Start the server unless it runs")
    parser.add_argument("commands", nargs="*")
    args = parser.parse_args()

    settings = dotenv_values(ROOT / ".env")
    port = int(settings.get("CS2_PORT") or 27015)
    address = listening_address(port)
    if address is None:
        if not args.start:
            raise SystemExit(f"nothing listens on port {port}; pass --start")
        address = start(settings, port)

    with RconClient(address, port, settings["RCON_PASSWORD"] or "") as client:
        for command in args.commands:
            print(f"=== {command} ===\n{client.execute(command)}", flush=True)


if __name__ == "__main__":
    main()
