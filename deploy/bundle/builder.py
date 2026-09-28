import json
import shutil
from pathlib import Path

from deploy.bundle.settings import SettingsRenderer
from deploy.config.inventory import Inventory
from deploy.config.secrets import ServerSecrets
from deploy.config.servers import Instance, Server
from deploy.errors import DeployError
from deploy.paths import PACKAGE_DIR, ROOT


class AddonsBuilder:
    """Assembles an instance's `addons` tree from the host, the plugins and rendered settings."""

    # The framework's install component, staged under build/package/ by the same name.
    HOST = "host"
    # Copied from voltmod.server.install, not imported: CI deploys install only the deploy group.
    HOST_ADDON_DIR = "voltmod"
    PLUGINS_DIR = f"{HOST_ADDON_DIR}/plugins"
    # The module the engine loads through gameinfo.gi; it starts the host.
    LOADER = f"{HOST_ADDON_DIR}/bin/linuxsteamrt64/libserver_valve.so"

    def __init__(self, inventory: Inventory, server: Server, secrets: ServerSecrets) -> None:
        self._server = server
        self._settings = SettingsRenderer(inventory, server, secrets)

    def build(self, instance: Instance, destination: Path) -> Path:
        """Rebuild destination/addons with the host and the instance's plugins, and return it."""
        addons = destination / "addons"
        shutil.rmtree(addons, ignore_errors=True)
        addons.mkdir(parents=True)
        # The host is in every payload: it loads only plugins built against its own ABI.
        self._unpack(self.HOST, addons)
        if not (addons / self.LOADER).is_file():
            raise DeployError(
                f"build/package/{self.HOST} has no {self.LOADER}; "
                "rebuild the framework and run `uv run poe deploy package`"
            )
        for plugin in self._server.plugins_for(instance):
            self._unpack(plugin, addons)
            self._write_configs(instance, plugin, addons)
        return addons

    def _write_configs(self, instance: Instance, plugin: str, addons: Path) -> None:
        """Copy the plugin's configs/ from the source tree, rendering settings.jsonc per server."""
        configs = addons / self.PLUGINS_DIR / plugin / "configs"
        shutil.copytree(ROOT / "plugins" / plugin / "configs", configs, dirs_exist_ok=True)
        settings = self._settings.render(instance, plugin)
        text = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
        (configs / "settings.jsonc").write_text(text, encoding="utf-8", newline="\n")

    @staticmethod
    def _unpack(name: str, addons: Path) -> None:
        package = PACKAGE_DIR / name / "addons"
        if not package.is_dir():
            raise DeployError(f"no package for {name}; run `uv run poe deploy package`")
        shutil.copytree(package, addons, dirs_exist_ok=True)
