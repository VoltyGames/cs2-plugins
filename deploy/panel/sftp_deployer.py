from collections.abc import Generator
from contextlib import contextmanager
from functools import cached_property

from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.config.servers import Instance, SftpServer
from deploy.deployer import Deployer
from deploy.panel.gameinfo import GameInfo
from deploy.panel.sftp import SftpFiles
from deploy.paths import RENDER_DIR


class SftpDeployer(Deployer[SftpServer]):
    """Uploads plugins over a panel node's SFTP, for panels that give no API key.

    Without the API it cannot stop or start the server, so the files load at its next restart.
    """

    @cached_property
    def files(self) -> SftpFiles:
        user = self.server.sftp_login(self.secrets.require("SFTP_USER"))
        return SftpFiles(self.server, user, self.secrets.require("SFTP_PASSWORD"))

    def deploy(self) -> None:
        instance = self.server.instance()
        game_dir = self.server.game_dir
        addons = self.addons.build(instance, RENDER_DIR / self.server.id)
        gameinfo = GameInfo.read(self.files, game_dir)
        self.print_plan(
            "Deploying",
            f"sftp:     {self.files.address}",
            f"host:     addons/{AddonsBuilder.HOST_ADDON_DIR}",
            f"gameinfo: {gameinfo.planned_change}",
            "restart:  from the panel, after the upload",
        )
        if self.dry_run:
            console.done("Dry run complete; the server was not changed")
            return

        gameinfo.write()
        uploaded = self.files.upload_tree(addons, f"{game_dir}/addons")
        console.item(f"uploaded {uploaded} files")
        unused = self.unused_plugin_paths(instance)
        if removed := self.files.delete(f"{game_dir}/addons/{AddonsBuilder.PLUGINS_DIR}", unused):
            console.item(f"removed unassigned plugins: {' '.join(removed)}")
        console.done(f"Deploy to {self.server.id} complete")
        console.warn(f"{self.server.id} runs the old plugins until you restart it from the panel")

    def restart(self) -> None:
        # Not an error, so `deploy restart` across every server carries on past this one.
        console.section(f"Restarting {self.server.id}")
        console.warn(f"{self.server.id} has no panel API key; restart it from the panel")

    @contextmanager
    def rcon_address(self, instance: Instance) -> Generator[tuple[str, int]]:
        # Panel servers expose RCON on the public game port.
        yield self.server.host, instance.port
