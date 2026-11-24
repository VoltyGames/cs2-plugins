import io
import stat
from pathlib import Path
from typing import IO, Self

import paramiko

from deploy.config.servers import SftpServer
from deploy.errors import DeployError


class SftpFiles:
    """A panel server's files over its node's SFTP, signed in with the panel account password."""

    def __init__(self, server: SftpServer, user: str, password: str) -> None:
        self.address = f"{user}@{server.sftp_address}:{server.sftp_port}"
        known_hosts = Path.home() / ".ssh" / "known_hosts"
        known_hosts.parent.mkdir(mode=0o700, exist_ok=True)
        known_hosts.touch(exist_ok=True)
        self._client = paramiko.SSHClient()
        self._client.load_host_keys(str(known_hosts))
        # Like ssh's accept-new: trust a node on first contact, refuse one whose key changed.
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._client.connect(
                server.sftp_address,
                server.sftp_port,
                username=user,
                password=password,
                look_for_keys=False,
                allow_agent=False,
                timeout=30,
            )
            self._sftp = self._client.open_sftp()
        except (paramiko.SSHException, OSError) as error:
            raise DeployError(f"SFTP sign-in to {self.address} failed: {error}") from None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    def read(self, path: str) -> str:
        """A file's text, or "" when it does not exist."""
        try:
            with self._sftp.open(path, "rb") as file:
                return file.read().decode()
        except FileNotFoundError:
            return ""

    def write(self, path: str, text: str) -> None:
        self._put(io.BytesIO(text.encode()), path)

    def delete(self, root: str, names: list[str]) -> list[str]:
        """Delete the entries under root that exist and return them."""
        present: list[str] = []
        for name in names:
            if attributes := self._find(f"{root}/{name}"):
                self._remove_tree(f"{root}/{name}", attributes)
                present.append(name)
        return present

    def is_link(self, path: str) -> bool:
        attributes = self._find(path)
        return bool(attributes and attributes.st_mode and stat.S_ISLNK(attributes.st_mode))

    def upload_tree(self, source: Path, destination: str) -> int:
        """Copy source's files into destination, keeping files already there; return the count."""
        self._make_dirs(destination)
        count = 0
        # Sorted, so each directory comes before what it holds.
        for local in sorted(source.rglob("*")):
            remote = f"{destination}/{local.relative_to(source).as_posix()}"
            if local.is_dir():
                if not self._find(remote):
                    self._sftp.mkdir(remote)
                continue
            with local.open("rb") as file:
                self._put(file, remote)
            count += 1
        return count

    def _put(self, data: IO[bytes], path: str) -> None:
        # Overwriting a loaded .so in place crashes the server; renamed over, it keeps the old one.
        staging = f"{path}.upload"
        self._sftp.putfo(data, staging, confirm=True)
        try:
            self._sftp.posix_rename(staging, path)
        except OSError:
            # Without the posix-rename extension, a plain rename refuses an existing target.
            if self._find(path):
                self._sftp.remove(path)
            self._sftp.rename(staging, path)

    def _make_dirs(self, path: str) -> None:
        current = ""
        for part in path.strip("/").split("/"):
            current = f"{current}/{part}"
            if not self._find(current):
                self._sftp.mkdir(current)

    def _remove_tree(self, path: str, attributes: paramiko.SFTPAttributes) -> None:
        if attributes.st_mode and stat.S_ISDIR(attributes.st_mode):
            for entry in self._sftp.listdir_attr(path):
                self._remove_tree(f"{path}/{entry.filename}", entry)
            self._sftp.rmdir(path)
        else:
            self._sftp.remove(path)

    def _find(self, path: str) -> paramiko.SFTPAttributes | None:
        try:
            return self._sftp.lstat(path)
        except FileNotFoundError:
            return None
