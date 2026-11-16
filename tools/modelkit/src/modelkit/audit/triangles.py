"""Triangles each part can lose without looking different, and trimming them."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from modelkit import headless
from modelkit.audit import Report, format_number
from modelkit.models import ModelFolder

# Worth trimming once this share of a part's triangles can go.
WORTHWHILE = 0.02


class Operation(StrEnum):
    DEGENERATE = "degenerate"
    COPLANAR = "coplanar"
    HIDDEN = "hidden"


@dataclass
class TriangleReport(Report):
    COLUMNS = ("model", "part", "tris", *Operation, "saving")
    model: str
    part: str
    triangles: int
    removable: dict[str, int]

    @property
    def saved(self) -> int:
        return sum(self.removable.values())

    @classmethod
    def read(cls, folder: ModelFolder, row: dict[str, Any]) -> Self:
        report = cls(folder.name, row["scene"], row["triangles"], row["removed"])
        if report.saved > report.triangles * WORTHWHILE:
            report.problems.append(f"{report.saved} can go")
        return report

    def cells(self) -> list[str]:
        return [
            self.model,
            self.part,
            str(self.triangles),
            *(str(self.removable.get(op, 0)) for op in Operation),
            f"{self.saved / max(self.triangles, 1):.1%}",
        ]


@dataclass
class TrimReport(TriangleReport):
    COLUMNS = (*TriangleReport.COLUMNS, "applied", "changed")
    applied: bool = False
    changed: float | None = None
    """The largest share of a view's pixels the trim changed."""

    @classmethod
    def read(cls, folder: ModelFolder, row: dict[str, Any]) -> Self:
        report = cls(folder.name, row["scene"], row["triangles"], row["removed"])
        report.applied, report.changed = row["applied"], row.get("changed")
        if not report.applied and report.changed:
            report.problems.append("rejected: a view changed")
        return report

    def cells(self) -> list[str]:
        applied = "yes" if self.applied else "no"
        return [*super().cells(), applied, format_number(self.changed, ".3%")]


def audit(folders: list[ModelFolder], operations: list[Operation]) -> list[TriangleReport]:
    def audit_folder(folder: ModelFolder) -> list[TriangleReport]:
        if not folder.blend.is_file():
            return []
        rows = headless.run_job("triangles", folder.blend, operations=operations)
        return [TriangleReport.read(folder, row) for row in rows]

    return [report for found in headless.run_each(audit_folder, folders) for report in found]


def optimize(folder: ModelFolder, views: Path, operations: list[Operation]) -> list[TrimReport]:
    """Trims the model's .blend where before/after renders, kept in `views`, match."""
    views.mkdir(parents=True, exist_ok=True)
    rows = headless.run_job(
        "triangles", folder.blend, operations=operations, apply=True, views_dir=str(views)
    )
    return [TrimReport.read(folder, row) for row in rows]
