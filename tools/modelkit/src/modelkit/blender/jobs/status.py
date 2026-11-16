"""Blender's version and whether Blender Source Tools is installed and enabled."""

from typing import Any

from modelkit.blender import session


def main() -> dict[str, Any]:
    return session.status()
