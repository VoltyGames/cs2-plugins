from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from modelkit import game
from modelkit.audit import find_models, textures
from modelkit.source2 import modeldoc


@pytest.fixture
def crate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The model folder of plugin "demo"'s "crate", under tmp_path."""
    monkeypatch.setattr(game, "plugin_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(game, "models_dir", lambda name: tmp_path / name / "content/models" / name)
    folder = tmp_path / "demo/content/models/demo/crate"
    folder.mkdir(parents=True)
    Image.fromarray(np.full((256, 256, 3), 90, np.uint8)).save(folder / "crate_color.png")
    return folder


def test_flat_material_is_flagged_and_team_colour_skipped(crate: Path) -> None:
    for name in ("crate", "team"):
        modeldoc.write_vmat(crate / f"{name}.vmat", "models/demo/crate/", "crate_color.png", "")
    modeldoc.write_vmdl(
        crate / "crate.vmdl",
        [("crate", "crate.dmx")],
        material_groups={"blue": {"models/demo/crate/team.vmat": "models/demo/crate/team.vmat"}},
    )
    [report] = textures.audit("demo", find_models("demo"))
    assert report.material == "crate.vmat"
    assert report.problems == ["flat colour", "one roughness", "no normal map", "no AO"]
