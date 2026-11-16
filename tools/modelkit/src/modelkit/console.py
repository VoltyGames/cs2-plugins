import re

from rich.console import Console
from rich.markup import escape
from rich.table import Table

_out = Console(highlight=False, soft_wrap=True)
_err = Console(stderr=True, highlight=False, soft_wrap=True)
if not _out.is_terminal:
    # Piped output, such as an agent reading it, would otherwise wrap tables at 80 columns.
    _out.width = 200


def info(text: str = "") -> None:
    _out.print(text, markup=False)


def check(ok: bool, what: str, detail: str = "") -> bool:
    """One tool check line: ok or MISSING."""
    status = "[green]ok     [/]" if ok else "[bold red]MISSING[/]"
    _out.print(f"{status} {escape(what)}{escape(f': {detail}') if detail else ''}")
    return ok


NUMBER = re.compile(r"[-\d.,x± %]*")


def table(title: str, columns: list[str], rows: list[list[str]], flagged: list[bool]) -> None:
    """A table whose flagged rows are highlighted; columns of numbers align right."""
    out = Table(title=title, title_justify="left", header_style="bold")
    for index, column in enumerate(columns):
        numeric = rows and all(NUMBER.fullmatch(row[index]) for row in rows)
        out.add_column(column, justify="right" if numeric else "left")
    for row, flag in zip(rows, flagged, strict=True):
        out.add_row(*map(escape, row), style="yellow" if flag else None)
    _out.print(out)


def done(text: str) -> None:
    _out.print(text, style="bold green", markup=False)


def error(text: str) -> None:
    _err.print(f"error: {text}", style="bold red", markup=False)
