import io
import tarfile
from collections.abc import Generator
from contextlib import contextmanager
from functools import cached_property

from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.config.servers import Instance, PanelServer
from deploy.deployer import Deployer
from deploy.errors import DeployError
from deploy.panel.api import PanelApi
from deploy.panel.gameinfo import GameInfo
from deploy.paths import RENDER_DIR


class PanelDeployer(Deployer[PanelServer]):
    """Uploads plugins through the panel API and restarts the server around the change."""

    @cached_property
    def api(self) -> PanelApi:
        return PanelApi(self.server, self.secrets.require("PANEL_API_KEY"))

    def deploy(self) -> None:
        instance = self.server.instance()
        game_dir = self.server.game_dir
        archive = self._plugin_archive(instance)
        gameinfo = GameInfo.read(self.api, game_dir)
        self.print_plan(
            "Deploying",
            f"panel:    {self.server.panel_url} ({self.api.state()})",
            f"payload:  {len(archive) // 1024} KiB",
            f"host:     addons/{AddonsBuilder.HOST_ADDON_DIR}",
            f"gameinfo: {gameinfo.planned_change}",
        )
        if self.dry_run:
            console.done("Dry run complete; the server was not changed")
            return

        gameinfo.write()
        self._stop()
        try:
            self.api.extract(game_dir, "cs2-plugins.tar.gz", archive)
            self._remove_unused_plugins(instance)
        except Exception:
            # A server running a partial install beats one left offline.
            console.error("deploy failed; starting the server again")
            self._start_after_failure()
            raise
        self._start()
        console.done(f"Deploy to {self.server.id} complete")

    def restart(self) -> None:
        self.print_plan("Restarting", f"panel: {self.server.panel_url}")
        if self.dry_run:
            console.done("Dry run complete; nothing restarted")
            return
        self._stop()
        self._start()
        console.done(f"Restart of {self.server.id} complete")

    @contextmanager
    def rcon_address(self, instance: Instance) -> Generator[tuple[str, int]]:
        # Panel servers expose RCON on the public game port.
        yield self.server.host, instance.port

    def _plugin_archive(self, instance: Instance) -> bytes:
        """The addons tree, unpacked into game/csgo."""
        addons = self.addons.build(instance, RENDER_DIR / self.server.id)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(addons, arcname="addons")
        return buffer.getvalue()

    def _remove_unused_plugins(self, instance: Instance) -> None:
        unused = self.unused_plugin_paths(instance)
        if removed := self.api.delete(
            f"{self.server.game_dir}/addons/{AddonsBuilder.PLUGINS_DIR}", unused
        ):
            console.item(f"removed unassigned plugins: {' '.join(removed)}")

    def _stop(self) -> None:
        # Overwriting a loaded .so can crash a running server.
        if self.api.state() == "offline":
            return
        console.item("stopping server")
        if not self.api.power("stop", "offline", 60) and not self.api.power("kill", "offline", 30):
            raise DeployError("server did not stop")

    def _start(self) -> None:
        console.item("starting server")
        if not self.api.power("start", "running", 600):
            raise DeployError("server did not start within 10 minutes; check the panel console")

    def _start_after_failure(self) -> None:
        """Start the server without hiding the error that stopped the deploy."""
        try:
            self._start()
        except DeployError as error:
            console.error(str(error))
