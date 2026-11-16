"""Reading a folder as it was at an earlier revision, Git LFS files resolved, without touching
the checkout."""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

LFS_POINTER = b"version https://git-lfs"


def run_git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    command = ["git", "-C", str(repo), *args]
    return subprocess.run(command, input=stdin, check=True, capture_output=True).stdout


def export_folder(repo: Path, folder: PurePosixPath, revision: str, into: Path) -> list[Path]:
    """Writes the files under `folder` at `revision` into `into`, flattened; returns them."""
    listed = (
        run_git(repo, "ls-tree", "-r", "--name-only", revision, str(folder)).decode().splitlines()
    )

    def export(name: str) -> Path:
        content = run_git(repo, "show", f"{revision}:{name}")
        if content.startswith(LFS_POINTER):
            content = run_git(repo, "lfs", "smudge", stdin=content)
        target = into / PurePosixPath(name).name
        target.write_bytes(content)
        return target

    into.mkdir(parents=True)
    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(export, listed))
