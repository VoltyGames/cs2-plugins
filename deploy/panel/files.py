from typing import Protocol


class ServerFiles(Protocol):
    """A panel server's files, through the panel API or the node's SFTP."""

    def read(self, path: str) -> str:
        """A file's text, or "" when it does not exist."""
        ...

    def write(self, path: str, text: str) -> None: ...

    def delete(self, root: str, names: list[str]) -> list[str]:
        """Delete the entries under root that exist and return them."""
        ...

    def is_link(self, path: str) -> bool: ...
