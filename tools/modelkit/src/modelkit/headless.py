"""Running modelkit.blender.jobs in a background Blender and reading their results."""

import json
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from modelkit import game

SOURCE = Path(__file__).resolve().parents[1]


class BlenderError(RuntimeError):
    pass


def run_job(job: str, blend: Path | None = None, user_settings: bool = False, **args: Any) -> Any:
    """Runs a job module's `main(**args)` in Blender, with `blend` open, and returns its result.

    Factory settings keep the user's add-ons out, unless `user_settings`, for jobs that need
    Blender Source Tools.
    """
    blender = game.find_blender()
    if blender is None:
        raise BlenderError("Blender not found; set BLENDER_PATH in .env")
    with tempfile.TemporaryDirectory(prefix="modelkit_") as scratch:
        args_path, result, log = (
            Path(scratch) / name for name in ("args.json", "result.json", "log.txt")
        )
        args_path.write_text(json.dumps(args), encoding="utf-8")
        code = (
            f"import sys; sys.path.insert(0, {str(SOURCE)!r}); "
            f"from modelkit.blender.jobs import run; "
            f"run({job!r}, {str(args_path)!r}, {str(result)!r})"
        )
        command = [str(blender), "--background"]
        command += [] if user_settings else ["--factory-startup"]
        command += [str(blend)] if blend else []
        command += ["--python-exit-code", "1", "--python-expr", code]
        with log.open("w", encoding="utf-8", errors="replace") as out:
            done = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
        if done.returncode or not result.exists():
            tail = "\n".join(
                log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-15:]
            )
            raise BlenderError(f"job {job} failed in {blend or 'Blender'}:\n{tail}")
        return json.loads(result.read_text(encoding="utf-8"))


def run_each[T, R](function: Callable[[T], R], items: Iterable[T], workers: int = 4) -> list[R]:
    """`function` over `items` in parallel threads, for jobs that each start their own Blender."""
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(function, items))
