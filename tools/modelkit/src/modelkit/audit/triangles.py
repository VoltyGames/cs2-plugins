"""Triangles each part can lose without looking different, and trimming them."""

from dataclasses import dataclass, field
from pathlib import Path

from modelkit import headless

OPERATIONS = ("degenerate", "coplanar", "hidden")
# Worth trimming once this share of a part's triangles can go.
WORTHWHILE = 0.02


@dataclass
class TriangleReport:
    model: str
    part: str
    triangles: int
    removable: dict[str, int]
    applied: bool | None = None
    changed: float | None = None
    """The largest share of a view's pixels the trim changed."""
    problems: list[str] = field(default_factory=list)

    @property
    def saved(self) -> int:
        return sum(self.removable.values())


def read_rows(folder: Path, rows: list[dict]) -> list[TriangleReport]:
    reports = []
    for row in rows:
        report = TriangleReport(
            model=folder.name,
            part=row["scene"],
            triangles=row["triangles"],
            removable=row["removed"],
            applied=row.get("applied"),
            changed=row.get("changed"),
        )
        if report.applied is None and report.saved > report.triangles * WORTHWHILE:
            report.problems.append(f"{report.saved} can go")
        if report.applied is False and report.changed:
            report.problems.append("rejected: a view changed")
        reports.append(report)
    return reports


def audit(folders: list[Path], operations: tuple[str, ...] = OPERATIONS) -> list[TriangleReport]:
    reports = []
    for folder in folders:
        blend = folder / f"{folder.name}.blend"
        if blend.is_file():
            rows = headless.run_job("triangles", blend, operations=list(operations))
            reports += read_rows(folder, rows)
    return reports


def optimize(
    folder: Path, views: Path, operations: tuple[str, ...] = OPERATIONS
) -> list[TriangleReport]:
    """Trims the model's .blend where before/after renders, kept in `views`, match."""
    views.mkdir(parents=True, exist_ok=True)
    rows = headless.run_job(
        "triangles",
        folder / f"{folder.name}.blend",
        apply=True,
        operations=list(operations),
        views_dir=str(views),
    )
    return read_rows(folder, rows)
