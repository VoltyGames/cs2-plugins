"""VPK archives: the file list in a version 2 directory file."""

import os


def list_files(path: str | os.PathLike[str]) -> list[str]:
    """Every file path in the VPK directory file at `path`, such as pak01_dir.vpk."""
    with open(path, "rb") as f:
        data = f.read()
    position = 28  # the header
    names = []

    def text() -> str:
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
                file = name if folder == " " else f"{folder}/{name}"
                names.append(f"{file}.{extension}")
    return names
