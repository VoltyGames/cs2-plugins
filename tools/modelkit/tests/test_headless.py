import pytest

from modelkit import game, headless


@pytest.mark.skipif(game.find_blender() is None, reason="Blender not installed")
def test_job_runs_in_background_blender() -> None:
    assert headless.run_job("status")["blender"]
