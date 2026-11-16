"""Particle effects outside Blender: check a .vpcf's field names, look up a particle class's
fields, and list the game's particle textures.

resourcecompiler drops a field it doesn't know without a word, so a misspelt field compiles into
an effect that lacks it. `check` and `fields` read the game's schema as dumped in
references/swiftlys2, which keys each field by the FNV-1a hashes of its class and its name.
"""

import os
import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path

from modelkit import game
from modelkit.source2 import kv3, vpk

SCHEMA = game.REPO / "references/swiftlys2/managed/src/SwiftlyS2.Generated/Schemas"

# The dump strips these from field names: m_flMaxLength is MaxLength there.
PREFIXES = ("m_", "m_fl", "m_f", "m_n", "m_i", "m_b", "m_vec", "m_v", "m_h", "m_psz", "m_str")
PROPERTY = re.compile(r"public (?:ref )?([\w<>, ]+?) (\w+) \{")


def fnv1a(text: str) -> int:
    value = 0x811C9DC5
    for byte in text.encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


@cache
def read_schema() -> tuple[dict[str, str], dict[str, list[tuple[str, str]]], set[int]]:
    """Each class's base, each class's (type, name) properties, and every declared field's key."""
    if not SCHEMA.is_dir():
        raise FileNotFoundError(f"no schema dump at {SCHEMA}")
    bases, properties, keys = {}, {}, set()
    for path in (SCHEMA / "Interfaces").glob("*.cs"):
        text = path.read_text(errors="ignore")
        if found := re.search(r"interface (\w+)\s*:\s*(\w+)", text):
            bases[found.group(1)] = found.group(2)
            properties[found.group(1)] = PROPERTY.findall(text)
    for path in (SCHEMA / "Classes").glob("*Impl.cs"):
        text = path.read_text(errors="ignore")
        keys.update(int(k, 16) for k in re.findall(r"GetOffset\(0x([0-9A-Fa-f]+)\)", text))
    return bases, properties, keys


def list_bases(cls: str) -> list[str]:
    """`cls` and its bases, nearest first; empty for a class the dump lacks."""
    bases = read_schema()[0]
    out = []
    while cls in bases and cls not in out:
        out.append(cls)
        cls = bases[cls]
    return out


def declares(cls: str, field: str) -> bool:
    return ((fnv1a(cls) << 32) | fnv1a(field)) in read_schema()[2]


def field_type(cls: str, field: str) -> str | None:
    """The type `cls` or a base gives `field`: None when none declares it, "" when untyped."""
    for owner in list_bases(cls):
        if declares(owner, field):
            for kind, name in read_schema()[1][owner]:
                if field.endswith(name) and field[: -len(name)] in PREFIXES:
                    return kind
            return ""
    return None


def list_fields(cls: str) -> list[tuple[str, str, str]]:
    """(declaring class, field, type) for `cls` and its bases; "?" marks a name not resolved."""
    rows = []
    for owner in list_bases(cls):
        for kind, name in read_schema()[1][owner]:
            real = next((p + name for p in PREFIXES if declares(owner, p + name)), "?" + name)
            rows.append((owner, real, kind))
    return rows


def element(kind: str) -> str:
    """The struct a field of type `kind` holds: a vector's element type, or the type itself."""
    inner = re.search(r"<\s*(\w+)", kind)
    return inner.group(1) if inner else kind


def unknown(node: dict[str, kv3.Parsed], cls: str, where: str) -> list[tuple[str, str, str]]:
    """(where, class, field) for each field under `node` that its class does not declare."""
    cls = node.get("_class", cls)
    found = []
    for key, child in node.items():
        if key == "_class":
            continue
        kind = field_type(cls, key)
        if kind is None:
            found.append((where, cls, key))
            continue
        for index, item in enumerate(child if isinstance(child, list) else [child]):
            inner = item.get("_class", element(kind)) if isinstance(item, dict) else ""
            if list_bases(inner):
                label = f"{where}.{key}[{index}]" if isinstance(child, list) else f"{where}.{key}"
                found += unknown(item, inner, label)
    return found


def check(paths: Iterable[str | os.PathLike[str]]) -> list[tuple[Path, str, str, str]]:
    """(file, where, class, field) for every unknown field in the .vpcf files at `paths`."""
    problems = []
    for path in map(Path, paths):
        tree = kv3.parse(path.read_text())
        problems += [(path, *found) for found in unknown(tree, "", "root")]
    return problems


def find_textures(word: str) -> list[str]:
    """The particle textures in the game's pak01 whose path holds `word`, as a .vpcf names them."""
    pak = game.client() / "game" / "csgo" / "pak01_dir.vpk"
    return sorted(
        name[:-2]
        for name in vpk.list_files(pak)
        if name.startswith("materials/particle") and name.endswith(".vtex_c") and word in name
    )
