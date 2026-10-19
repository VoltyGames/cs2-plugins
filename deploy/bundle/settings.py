import json
import re
from pathlib import Path
from typing import Any

from deploy.config.inventory import Inventory
from deploy.config.secrets import ServerSecrets
from deploy.config.servers import Instance, Server
from deploy.errors import DeployError
from deploy.paths import ROOT


class SettingsRenderer:
    """A plugin's own settings.jsonc with inventory overrides and its database filled in."""

    PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    # Strings match first, so `//` inside a URL survives comment removal.
    COMMENT_OR_STRING = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)

    def __init__(self, inventory: Inventory, server: Server, secrets: ServerSecrets) -> None:
        self._inventory = inventory
        self._server = server
        self._secrets = secrets

    def render(self, instance: Instance, plugin: str) -> dict[str, Any]:
        configs = ROOT / "plugins" / plugin / "configs"
        settings = self._read_jsonc(configs / "settings.jsonc")
        variables = {
            **self._secrets.as_dict(),
            # Per-server admin grants reference the tag, so it must stay stable.
            "SERVER_TAG": f"{self._server.id}-{instance.name}",
            "SERVER_NAME": instance.server_name,
        }
        config = self._inventory.plugins[plugin]
        self._override(settings, self._substitute(config.settings, variables, plugin), plugin)
        if config.database:
            database = self._database(config.database)
            settings["database"] = {**settings.get("database", {}), **database}
        return settings

    def _read_jsonc(self, path: Path) -> Any:
        if not path.is_file():
            raise DeployError(f"no plugin settings at {path.relative_to(ROOT).as_posix()}")
        text = self.COMMENT_OR_STRING.sub(self._keep_strings, path.read_text())
        return json.loads(text)

    @staticmethod
    def _keep_strings(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0).startswith('"') else ""

    def _substitute(self, value: Any, variables: dict[str, str], plugin: str) -> Any:
        """Replace ${NAME} in every string inside value; an unknown name fails."""
        if isinstance(value, dict):
            return {key: self._substitute(item, variables, plugin) for key, item in value.items()}
        if isinstance(value, list):
            return [self._substitute(item, variables, plugin) for item in value]
        if not isinstance(value, str):
            return value
        for name in self.PLACEHOLDER.findall(value):
            if name not in variables:
                raise DeployError(f"${{{name}}} in the {plugin} settings is not set")
        return self.PLACEHOLDER.sub(lambda match: variables[match.group(1)], value)

    def _override(
        self,
        settings: dict[str, Any],
        overrides: dict[str, Any],
        plugin: str,
        prefix: str = "",
    ) -> None:
        """Deep-merge overrides; lists and scalars replace. A key the plugin's file lacks fails."""
        for key, value in overrides.items():
            if key not in settings:
                raise DeployError(f"inventory sets unknown {plugin} setting '{prefix}{key}'")
            if isinstance(value, dict) and isinstance(settings[key], dict):
                self._override(settings[key], value, plugin, f"{prefix}{key}.")
            else:
                settings[key] = value

    def _database(self, name: str) -> dict[str, Any]:
        database = self._inventory.database
        host = self._secrets.get("DB_HOST", database.host or "")
        if not host:
            raise DeployError(f"DB_HOST is not set for {self._server.id}")
        return {
            "host": host,
            "port": database.port,
            "database": name,
            "username": database.user,
            "password": self._secrets.require("DB_PASSWORD"),
            "sslMode": database.ssl_mode,
        }
