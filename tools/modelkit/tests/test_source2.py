import struct
from pathlib import Path

from modelkit.source2 import kv3, modeldoc, vpk, vtex


def test_kv3_round_trip() -> None:
    value = {
        "scale": 0.8,
        "looping": True,
        "origin": [0.0, 1.5, 2.0],
        "texture": kv3.Resource("materials/particle/glow.vtex"),
        "children": [{"_class": "Node", "children": []}],
    }
    parsed = kv3.parse(kv3.write(value))
    assert parsed["scale"] == "0.8"
    assert parsed["texture"] == "materials/particle/glow.vtex"
    assert parsed["children"] == [{"_class": "Node", "children": []}]


def test_vmdl_reads_back_meshes_scale_and_team_materials(tmp_path: Path) -> None:
    path = modeldoc.write_vmdl(
        tmp_path / "tank.vmdl",
        [("tank", "tank.dmx")],
        material_groups={
            "blue": {"models/x/team.vmat": "models/x/team.vmat"},
            "red": {"models/x/team.vmat": "models/x/team_red.vmat"},
        },
        scale=0.8,
    )
    model = modeldoc.read_vmdl(path)
    assert model.meshes == ["tank.dmx"]
    assert model.scale == 0.8
    assert model.swapped == {"models/x/team.vmat", "models/x/team_red.vmat"}


def test_vtex_reads_size_from_data_block(tmp_path: Path) -> None:
    body = struct.pack("<HH4fHHHBB", 1, 0, 0.5, 0.5, 0.5, 0.5, 2048, 1024, 1, 20, 10)
    header = struct.pack("<IHHII", 0, 12, 0, 8, 1)  # one block entry right after the header
    entry = b"DATA" + struct.pack("<II", 8, len(body))  # the body follows the entry
    path = tmp_path / "pad_color_png_123.vtex_c"
    path.write_bytes(header + entry + body)
    texture = vtex.read(path)
    assert (texture.width, texture.height, texture.mip_levels) == (2048, 1024, 10)


def test_vpk_lists_files(tmp_path: Path) -> None:
    record = struct.pack("<IHHIIH", 0, 0, 0, 0, 0, 0xFFFF)
    tree = b"vtex_c\0materials/particle\0glow\0" + record + b"\0 \0root\0" + record + b"\0\0\0"
    path = tmp_path / "pak01_dir.vpk"
    path.write_bytes(bytes(28) + tree)
    assert vpk.list_files(path) == ["materials/particle/glow.vtex_c", "root.vtex_c"]
