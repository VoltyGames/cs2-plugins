"""How well a model's UVs use its textures: texel density at the size the game loads, atlas
fill, overlap and faces left without UV area."""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from modelkit import game, headless
from modelkit.audit import (
    SOLID_COLOUR,
    find_source,
    read_materials,
    read_png_size,
    shipped_size,
)
from modelkit.source2 import modeldoc

# A player sees a prop from 60-80 units at 1080p and 90 degrees: about 14 screen pixels a unit.
DEFAULT_TARGET = 12.0
LOW_FILL = 0.6
NO_AREA = 0.02
UNEVEN = 2.0


@dataclass
class UvReport:
    model: str
    part: str
    material: str
    shipped: tuple[int, int]
    triangles: int
    density: float
    p10: float
    p90: float
    coverage: float | None
    overlap: float | None
    span: float
    no_area: float
    problems: list[str] = field(default_factory=list)


def scales_by_mesh(folder: Path) -> dict[str, float]:
    """Each render mesh DMX stem's model scale, from the folder's .vmdl files."""
    scales = {}
    for vmdl in folder.glob("*.vmdl"):
        model = modeldoc.read_vmdl(vmdl)
        scales |= {PurePosixPath(mesh).stem: model.scale for mesh in model.meshes}
    return scales


def colour_sizes(plugin: str, folder: Path) -> dict[str, tuple[int, int]]:
    """Each textured material's colour texture size; accents and solid colours left out."""
    sizes = {}
    for material in read_materials(folder):
        color = find_source(plugin, material.keys.get("TextureColor", ""))
        if color and not material.accent and max(size := read_png_size(color)) > SOLID_COLOUR:
            sizes[material.name] = size
    return sizes


def judge(report: UvReport, target: float) -> None:
    if report.density < target:
        report.problems.append(f"density under {target:g}")
    if report.coverage is not None and report.coverage < LOW_FILL:
        report.problems.append(f"atlas {report.coverage:.0%} full")
    if report.no_area > NO_AREA:
        report.problems.append(f"{report.no_area:.0%} of surface without UV area")
    if report.p10 and report.p90 / report.p10 > UNEVEN:
        report.problems.append("uneven density")


def audit_model(plugin: str, folder: Path, target: float, cap: int | None) -> list[UvReport]:
    blend = folder / f"{folder.name}.blend"
    if not blend.is_file():
        return []
    scales = scales_by_mesh(folder)
    sizes = colour_sizes(plugin, folder)
    reports = []
    for row in headless.run_job("uv_report", blend):
        if row["material"] not in sizes:
            continue
        shipped = shipped_size(sizes[row["material"]], cap)
        pixels = (shipped[0] * shipped[1]) ** 0.5 / scales.get(row["dmx"], 1.0)
        report = UvReport(
            model=folder.name,
            part=row["scene"],
            material=row["material"],
            shipped=shipped,
            triangles=row["triangles"],
            density=row["density"] * pixels,
            p10=row["p10"] * pixels,
            p90=row["p90"] * pixels,
            coverage=row["coverage"],
            overlap=row["overlap"],
            span=row["span"],
            no_area=row["zero_share"],
        )
        judge(report, target)
        reports.append(report)
    return reports


def audit(plugin: str, folders: list[Path], target: float = DEFAULT_TARGET) -> list[UvReport]:
    cap = game.read_texture_cap()
    return [r for folder in folders for r in audit_model(plugin, folder, target, cap)]
