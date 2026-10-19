"""Build the Linux plugins in a local CI container copy and stage them under build/package/."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[3]
CHECKOUT = ROOT / "voltmod"
SEED = ROOT / "build" / "linux-seed"
OWN_RECIPES = ("voltmod", "sqlpp23", "s2sdk", "khook")


def git(*args: str) -> str:
    command = ["git", "-C", str(CHECKOUT), *args]
    return subprocess.run(command, capture_output=True, text=True).stdout.strip()


def locked_references() -> list[str]:
    """Every `name/version#revision` conan.lock pins, across its requires sections."""
    lock = json.loads((ROOT / "conan.lock").read_text())
    pins = [item for value in lock.values() if isinstance(value, list) for item in value]
    return [pin.split("%")[0] for pin in pins]


def checkout_differs_from_lock(references: list[str]) -> bool:
    """True when voltmod is anything but a clean checkout of the release conan.lock pins."""
    pinned = next((item for item in references if item.startswith("voltmod/")), None)
    if pinned is None or git("status", "--porcelain"):
        return True
    version = pinned.removeprefix("voltmod/").split("#")[0]
    return git("describe", "--tags", "--exact-match") != f"v{version}"


def seed_local_revisions(references: list[str]) -> None:
    """Save the locked revisions of our own recipes from this machine's Conan cache.

    A local relock pins revisions that no remote has; the container restores them from here.
    """
    shutil.rmtree(SEED, ignore_errors=True)
    SEED.mkdir(parents=True)
    for reference in references:
        name = reference.split("/")[0]
        if name not in OWN_RECIPES:
            continue
        save = ["conan", "cache", "save", reference, "--file", str(SEED / f"{name}.tgz")]
        # Not in the local cache means it came from a remote, where the container finds it too.
        subprocess.run(save, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--framework",
        choices=["auto", "checkout", "locked"],
        default="auto",
        help="checkout: build voltmod too; locked: the release conan.lock pins; "
        "auto: checkout when it differs from that release",
    )
    parser.add_argument("--test", action="store_true", help="Run CTest after the build")
    parser.add_argument("--rebuild-image", action="store_true")
    args = parser.parse_args()

    references = locked_references()
    framework = args.framework
    if framework == "auto":
        framework = "checkout" if checkout_differs_from_lock(references) else "locked"
    print(f"=== Framework: {framework} ===", flush=True)
    seed_local_revisions(references)

    # fmt: off
    run = [
        "docker", "compose", "-f", str(SCRIPTS / "docker-compose.yml"),
        "run", "--rm", *(["--build"] if args.rebuild_image else []), "build",
    ]
    # fmt: on
    environment = {**os.environ, "FRAMEWORK": framework, "RUN_TESTS": str(int(args.test))}
    sys.exit(subprocess.run(run, env=environment).returncode)


if __name__ == "__main__":
    main()
