"""Compiled textures (.vtex_c): the size the game actually loads."""

import os
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class CompiledTexture:
    width: int
    height: int
    mip_levels: int


def read(path: str | os.PathLike[str]) -> CompiledTexture:
    """The size, format and mip count in a .vtex_c's DATA block."""
    with open(path, "rb") as f:
        data = f.read()
    block_offset, block_count = struct.unpack_from("<II", data, 8)
    first = 8 + block_offset
    for index in range(block_count):
        entry = first + index * 12
        if data[entry : entry + 4] == b"DATA":
            offset = struct.unpack_from("<I", data, entry + 4)[0]
            body = entry + 4 + offset
            # Version and flags, then four reflectivity floats, then the size.
            width, height = struct.unpack_from("<HH", data, body + 20)
            return CompiledTexture(width, height, data[body + 27])
    raise ValueError(f"{path} has no DATA block")
