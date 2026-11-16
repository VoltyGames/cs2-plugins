"""Running modelkit.blender.jobs in a background Blender and reading their results."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from modelkit import game

SOURCE = Path(__file__).resolve().parents[1]


class BlenderError(RuntimeError):
    pass


def run_job(job: str, blend: Path | None = None, user_settings: bool = False, **args: Any) -> Any:
    """Runs a job module's `main(**args)` in Blender, with `blend` open, and returns its result.

    Factory settings keep the user's add-ons and preferences out, unless `user_settings`, which a
    job checking the user's add-ons needs.
    """
    blender = game.find_blender()
    if blender is None:
        raise BlenderError("Blender not found; set BLENDER_PATH in .env")
    with tempfile.TemporaryDirectory(prefix="modelkit_") as scratch:
        result = Path(scratch) / "result.json"
        code = (
            f"import sys; sys.path.insert(0, {str(SOURCE)!r}); "
            f"from modelkit.blender.jobs import run; "
            f"run({job!r}, {json.dumps(args)!r}, {str(result)!r})"
        )
        command = [str(blender), "--background"]
        command += [] if user_settings else ["--factory-startup"]
        command += [str(blend)] if blend else []
        command += ["--python-exit-code", "1", "--python-expr", code]
        done = subprocess.run(command, capture_output=True, text=True, errors="replace")
        if done.returncode or not result.exists():
            tail = "\n".join((done.stderr or done.stdout).strip().splitlines()[-15:])
            raise BlenderError(f"job {job} failed in {blend or 'Blender'}:\n{tail}")
        return json.loads(result.read_text(encoding="utf-8"))
