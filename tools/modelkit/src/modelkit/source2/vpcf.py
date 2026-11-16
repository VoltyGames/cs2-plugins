"""Particle systems (.vpcf). The compiler drops a field it doesn't know, so run
`modelkit particles check` on what this writes."""

import os
from collections.abc import Iterable, Sequence

from modelkit.source2.kv3 import Resource, Value, write

type FilePath = str | os.PathLike[str]
type Node = dict[str, Value]

HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:vpcf66:version{dd571be4-586e-4f41-8b2d-5bbc969e1c53} -->\n"
)


def write_vpcf(
    path: FilePath,
    emitters: Iterable[Node],
    initializers: Iterable[Node],
    operators: Iterable[Node],
    renderers: Iterable[Node],
    children: Sequence[str] = (),
    **fields: Value,
) -> FilePath:
    """Writes a particle system of `op(...)` nodes; `children` are .vpcf paths started with it,
    `fields` the system's own, and a texture a `Resource`."""
    system = {
        "_class": "CParticleSystemDefinition",
        "m_nBehaviorVersion": 12,
        **fields,
        "m_Emitters": list(emitters),
        "m_Initializers": list(initializers),
        "m_Operators": list(operators),
        "m_Renderers": list(renderers),
    }
    if children:
        system["m_Children"] = [{"m_ChildRef": Resource(child)} for child in children]
    with open(path, "w", newline="\n") as f:
        f.write(HEADER + write(system) + "\n")
    return path


def op(cls: str, **fields: Value) -> Node:
    """One emitter, initializer, operator or renderer, e.g. op("C_OP_Decay")."""
    return {"_class": cls, **fields}


def literal(value: float) -> Node:
    """A fixed number where the field takes an input, such as an emitter's particle count."""
    return {"m_nType": "PF_TYPE_LITERAL", "m_flLiteralValue": float(value)}


def vector(x: float, y: float, z: float) -> Node:
    """A fixed vector where the field takes an input, such as a velocity bound."""
    return {"m_nType": "PVEC_TYPE_LITERAL", "m_vLiteralValue": [float(x), float(y), float(z)]}
