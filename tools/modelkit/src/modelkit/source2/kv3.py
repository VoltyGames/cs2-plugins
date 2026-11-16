"""KeyValues3 text: writing the files the compiler reads, and parsing them back."""

import re


class Resource(str):
    """A path to another compiled file, such as a particle's texture or child effect."""


type Value = dict[str, Value] | list[Value] | bool | int | float | str
type Parsed = dict[str, Parsed] | list[Parsed] | str


# Comments, punctuation, strings with an optional resource: prefix, and bare words or numbers.
TOKEN = re.compile(
    r'//[^\n]*|<!--.*?-->|[{}\[\]=,]|(?:\w+:)?"(?:[^"\\]|\\.)*"|[^\s{}\[\]=,]+', re.DOTALL
)


def write(value: Value, depth: int = 0) -> str:
    """`value` as KV3 text: dicts, lists, bools, numbers, strings and Resources."""
    pad = "\t" * depth
    if isinstance(value, dict):
        fields = "".join(f"{pad}\t{k} = {write(v, depth + 1)}\n" for k, v in value.items())
        return "{\n" + fields + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[  ]"
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return "[ " + ", ".join(write(v) for v in value) + " ]"
        return "[\n" + "".join(f"{pad}\t{write(v, depth + 1)},\n" for v in value) + pad + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0")
        return text + "0" if text.endswith(".") else text
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Resource):
        return f'resource:"{value}"'
    return f'"{value}"'


def parse(text: str) -> Parsed:
    """The value tree of a KV3 text file. Strings lose their quotes and any resource: prefix;
    numbers stay strings."""
    tokens = [t for t in TOKEN.findall(text) if not t.startswith(("//", "<!--"))]
    position = 0

    def value() -> Parsed:
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
