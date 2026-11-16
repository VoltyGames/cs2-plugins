"""The modelkit command line: uv run modelkit <command>."""

import subprocess

from modelkit import console
from modelkit.cli import audit, models, particles
from modelkit.cli.app import app
from modelkit.headless import BlenderError

__all__ = ["app", "audit", "main", "models", "particles"]

# Failures a user can act on: one line instead of a traceback.
EXPECTED = (BlenderError, FileNotFoundError, ValueError)


def main() -> None:
    try:
        app()
    except EXPECTED as failed:
        console.error(str(failed))
        raise SystemExit(1) from None
    except subprocess.CalledProcessError as failed:
        console.error(f"{failed.cmd[0]}: {failed.stderr.decode(errors='replace').strip()}")
        raise SystemExit(1) from None
