"""Particle effects outside Blender: check a .vpcf's field names, look up a particle class's
fields, and list the game's particle textures.

Usage:
    uv run python .claude/skills/3d-model/scripts/particles.py check <file.vpcf>...
    uv run python .claude/skills/3d-model/scripts/particles.py fields <class>
    uv run python .claude/skills/3d-model/scripts/particles.py textures [word]

resourcecompiler drops a field it doesn't know without a word, so a misspelt field compiles into
an effect that lacks it. `check` and `fields` read the game's schema as dumped in
references/swiftlys2, which keys each field by the FNV-1a hashes of its class and its name.
"""

import argparse
import re
import sys
from functools import cache
from pathlib import Path

lazy from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[4]
SCHEMA = ROOT / "references/swiftlys2/managed/src/SwiftlyS2.Generated/Schemas"
DEFAULT_CLIENT = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
# The dump strips these from field names: m_flMaxLength is MaxLength there.
PREFIXES = ("m_", "m_fl", "m_f", "m_n", "m_i", "m_b", "m_vec", "m_v", "m_h", "m_psz", "m_str")
PROPERTY = re.compile(r"public (?:ref )?([\w<>, ]+?) (\w+) \{")
# Comments, punctuation, strings with an optional resource: prefix, and bare words or numbers.
TOKEN = re.compile(
    r'//[^\n]*|<!--.*?-->|[{}\[\]=,]|(?:\w+:)?"(?:[^"\\]|\\.)*"|[^\s{}\[\]=,]+', re.DOTALL
)


def fnv1a(text):
    value = 0x811C9DC5
    for byte in text.encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


@cache
def schema():
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


def lineage(cls):
    """`cls` and its bases, nearest first; empty for a class the dump lacks."""
    bases = schema()[0]
    out = []
    while cls in bases and cls not in out:
        out.append(cls)
        cls = bases[cls]
    return out


def declares(cls, field):
    return ((fnv1a(cls) << 32) | fnv1a(field)) in schema()[2]


def field_type(cls, field):
    """The type `cls` or a base gives `field`: None when none declares it, "" when untyped."""
    for owner in lineage(cls):
        if declares(owner, field):
            for kind, name in schema()[1][owner]:
                if field.endswith(name) and field[: -len(name)] in PREFIXES:
                    return kind
            return ""
    return None


def fields(cls):
    """(declaring class, field, type) for `cls` and its bases; "?" marks a name not resolved."""
    rows = []
    for owner in lineage(cls):
        for kind, name in schema()[1][owner]:
            real = next((p + name for p in PREFIXES if declares(owner, p + name)), "?" + name)
            rows.append((owner, real, kind))
    return rows


def parse(text):
    """The value tree of a KV3 text file. Strings lose their quotes and any resource: prefix."""
    tokens = [t for t in TOKEN.findall(text) if not t.startswith(("//", "<!--"))]
    position = 0

    def value():
        nonlocal position
        token = tokens[position]
        position += 1
        if token == "{":
            node = {}
            while tokens[position] != "}":
                key = tokens[position].strip('"')
                position += 2  # the key and its "="
                node[key] = value()
            position += 1
            return node
        if token == "[":
            items = []
            while tokens[position] != "]":
                if tokens[position] == ",":
                    position += 1
                else:
                    items.append(value())
            position += 1
            return items
        quoted = re.fullmatch(r'(?:\w+:)?"(.*)"', token, re.DOTALL)
        return quoted.group(1) if quoted else token

    return value()


def element(kind):
    """The struct a field of type `kind` holds: a vector's element type, or the type itself."""
    inner = re.search(r"<\s*(\w+)", kind)
    return inner.group(1) if inner else kind


def unknown(node, cls, where):
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
            if lineage(inner):
                label = f"{where}.{key}[{index}]" if isinstance(child, list) else f"{where}.{key}"
                found += unknown(item, inner, label)
    return found


def check(paths):
    """(file, where, class, field) for every unknown field in the .vpcf files at `paths`."""
    problems = []
    for path in map(Path, paths):
        tree = parse(path.read_text())
        problems += [(path, *found) for found in unknown(tree, "", "root")]
    return problems


def packed(pak):
    """Every file path in a version 2 VPK directory file."""
    data = pak.read_bytes()
    position = 28  # the header
    names = []

    def text():
        nonlocal position
        end = data.index(b"\0", position)
        value = data[position:end].decode(errors="ignore")
        position = end + 1
        return value

    while extension := text():
        while folder := text():
            while name := text():
                preload = int.from_bytes(data[position + 4 : position + 6], "little")
                position += 18 + preload  # the entry record, then its preloaded bytes
                path = name if folder == " " else f"{folder}/{name}"
                names.append(f"{path}.{extension}")
    return names


def textures(word):
    """The particle textures in the game's pak01 whose path holds `word`, as a .vpcf names them."""
    client = dotenv_values(ROOT / ".env").get("CS2_CLIENT_PATH") or DEFAULT_CLIENT
    return sorted(
        name[:-2]
        for name in packed(Path(client) / "game" / "csgo" / "pak01_dir.vpk")
        if name.startswith("materials/particle") and name.endswith(".vtex_c") and word in name
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check").add_argument("files", nargs="+", type=Path)
    commands.add_parser("fields").add_argument("cls")
    commands.add_parser("textures").add_argument("word", nargs="?", default="")
    args = parser.parse_args()

    if args.command == "textures":
        print("\n".join(textures(args.word)))
        return 0
    try:
        if args.command == "fields":
            rows = fields(args.cls)
            for owner, name, kind in rows:
                print(f"{owner:34} {name:40} {kind}")
            return 0 if rows else f"no class {args.cls} in the schema dump"
        problems = check(args.files)
    except FileNotFoundError as missing:
        return str(missing)
    for path, where, cls, field in problems:
        print(f"{path}: {where}: {cls} has no field {field}")
    print(f"{len(problems)} unknown field(s) in {len(args.files)} file(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
