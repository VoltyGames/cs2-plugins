"""Audits of a plugin's models: their textures, their UVs, their triangles and what the
compiler shipped."""

from dataclasses import dataclass, field
from typing import ClassVar


def format_size(value: tuple[int, int] | None) -> str:
    return f"{value[0]}x{value[1]}" if value else "-"


def format_number(value: float | None, spec: str) -> str:
    return "-" if value is None else format(value, spec)


@dataclass(kw_only=True)
class Report:
    """One audited row; COLUMNS name what `cells()` returns, before the problems column."""

    COLUMNS: ClassVar[tuple[str, ...]]
    problems: list[str] = field(default_factory=list)

    def cells(self) -> list[str]:
        raise NotImplementedError
