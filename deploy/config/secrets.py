import os

from dotenv import dotenv_values

from deploy.errors import DeployError
from deploy.paths import DEPLOY_DIR, ROOT


class ServerSecrets:
    """A server's secrets from its .env file, which CI writes; the process env fills gaps."""

    def __init__(self, folder: str) -> None:
        self.file = DEPLOY_DIR / "secrets" / folder / ".env"
        values = dotenv_values(self.file) if self.file.is_file() else {}
        self._values = {**os.environ, **{name: value or "" for name, value in values.items()}}
        # CI names its own key file in the process env; a local path copied into the file loses.
        if key_file := os.environ.get("SSH_KEY_FILE"):
            self._values["SSH_KEY_FILE"] = key_file

    def get(self, name: str, default: str = "") -> str:
        return self._values.get(name) or default

    def require(self, name: str) -> str:
        if value := self._values.get(name):
            return value
        location = self.file.relative_to(ROOT).as_posix()
        raise DeployError(f"{name} is not set in {location}")

    def as_dict(self) -> dict[str, str]:
        return dict(self._values)
