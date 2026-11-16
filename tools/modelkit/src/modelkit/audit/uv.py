"""How well a model's UVs use its textures: texel density at the size the game loads, atlas
fill, overlap and faces left without UV area."""

from dataclasses import dataclass
from typing import Any

from modelkit import game, headless
from modelkit.audit import Report, format_number, format_size
from modelkit.models import ModelFolder, read_image_size

# A player sees a prop from 60-80 units at 1080p and 90 degrees: about 14 screen pixels a unit.
TARGET_DENSITY = 12.0
LOW_FILL = 0.6
NO_AREA = 0.02
UNEVEN = 2.0


@dataclass
class UvReport(Report):
    COLUMNS = (
        "model",
        "part",
        "material",
        "shipped",
        "tris",
        "density",
        "p10-p90",
        "fill",
        "overlap",
        "span",
    )
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

    def cells(self) -> list[str]:
        return [
            self.model,
            self.part,
            self.material,
            format_size(self.shipped),
            str(self.triangles),
            f"{self.density:.1f}",
            f"{self.p10:.1f}-{self.p90:.1f}",
            format_number(self.coverage, ".0%"),
            format_number(self.overlap, ".2f"),
            "-" if self.coverage is not None else f"{self.span:.1f}",
        ]

    def judge(self, target: float) -> None:
        if self.density < target:
            self.problems.append(f"density under {target:g}")
        if self.coverage is not None and self.coverage < LOW_FILL:
            self.problems.append(f"atlas {self.coverage:.0%} full")
        if self.no_area > NO_AREA:
            self.problems.append(f"{self.no_area:.0%} of surface without UV area")
        if self.p10 and self.p90 / self.p10 > UNEVEN:
            self.problems.append("uneven density")


def shrink_to_cap(size: tuple[int, int], cap: int | None) -> tuple[int, int]:
    """The size the compiler writes: the longest side clamped to `cap`, aspect kept."""
    if not cap or max(size) <= cap:
        return size
    factor = cap / max(size)
    return max(1, round(size[0] * factor)), max(1, round(size[1] * factor))


def read_colour_sizes(folder: ModelFolder) -> dict[str, tuple[int, int]]:
    """Each textured material's colour texture size; accents and solid colours left out."""
    return {
        material.name: read_image_size(color)
        for material in folder.materials
        if not material.accent and (color := material.find_detailed_texture("TextureColor"))
    }


def read_row(
    folder: ModelFolder, row: dict[str, Any], shipped: tuple[int, int], scale: float
) -> UvReport:
    pixels = (shipped[0] * shipped[1]) ** 0.5 / scale
    return UvReport(
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


def audit(folders: list[ModelFolder], target: float = TARGET_DENSITY) -> list[UvReport]:
    cap = game.read_texture_cap()

    def audit_folder(folder: ModelFolder) -> list[UvReport]:
        if not folder.blend.is_file():
            return []
        scales, sizes = folder.read_scales(), read_colour_sizes(folder)
        reports = []
        for row in headless.run_job("uv_report", folder.blend):
            if row["material"] in sizes:
                shipped = shrink_to_cap(sizes[row["material"]], cap)
                report = read_row(folder, row, shipped, scales.get(row["dmx"], 1.0))
                report.judge(target)
                reports.append(report)
        return reports

    return [report for found in headless.run_each(audit_folder, folders) for report in found]
