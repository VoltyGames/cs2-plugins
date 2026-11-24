import re
from typing import Self

from deploy.errors import DeployError
from deploy.panel.files import ServerFiles
from deploy.paths import FILES_DIR


class GameInfo:
    """A panel server's csgo/gameinfo.gi, which must list VoltMod's search path."""

    SEARCH_PATH = "csgo/addons/voltmod"
    GAME_CSGO_LINE = re.compile(r"^([ \t]*)Game[ \t]+csgo[ \t]*(\r?)$", re.MULTILINE)
    # Valve's file from an up-to-date dedicated server; refresh it when a CS2 update changes it.
    TEMPLATE = FILES_DIR / "panel" / "gameinfo.gi"

    def __init__(
        self, files: ServerFiles, game_dir: str, current: str, shared_install: bool
    ) -> None:
        self._files = files
        self._game_dir = game_dir
        self.current = current
        self.shared_install = shared_install
        source = self.TEMPLATE.read_bytes().decode() if shared_install else current
        self.patched = self.with_voltmod(source)

    @classmethod
    def read(cls, files: ServerFiles, game_dir: str) -> Self:
        # Hosts that link every server to one shared CS2 install refuse to read those links.
        if files.is_link(f"{game_dir}/steam.inf"):
            return cls(files, game_dir, "", shared_install=True)
        current = files.read(f"{game_dir}/gameinfo.gi")
        if not current:
            raise DeployError(f"{game_dir}/gameinfo.gi not found; is CS2 installed there?")
        return cls(files, game_dir, current, shared_install=False)

    @classmethod
    def with_voltmod(cls, text: str) -> str:
        """`text` with VoltMod's search path directly above the first `Game csgo` line."""
        if cls.SEARCH_PATH in text:
            return text
        replacement = rf"\1Game\t{cls.SEARCH_PATH}\2\n\g<0>"
        patched, count = cls.GAME_CSGO_LINE.subn(replacement, text, count=1)
        if not count:
            raise DeployError("gameinfo.gi has no `Game csgo` line; its format changed")
        return patched

    @property
    def planned_change(self) -> str:
        if self.shared_install:
            return "template"
        return "patch" if self.patched != self.current else "ok"

    def write(self) -> None:
        """Save the patched file; CS2 reads it only at startup, so it is safe while running."""
        if self.shared_install:
            self._files.delete(self._game_dir, ["gameinfo.gi"])
        if self.patched != self.current:
            self._files.write(f"{self._game_dir}/gameinfo.gi", self.patched)
