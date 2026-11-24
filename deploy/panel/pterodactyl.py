from collections.abc import Generator
from contextlib import contextmanager

from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.config.servers import Instance, PterodactylServer
from deploy.deployer import Deployer
from deploy.panel.files import ServerFiles


class PterodactylDeployer[S: PterodactylServer](Deployer[S]):
    """Steps shared by Pterodactyl servers, whether reached by the panel API or SFTP."""

    @contextmanager
    def rcon_address(self, instance: Instance) -> Generator[tuple[str, int]]:
        # Panel servers expose RCON on the public game port.
        yield self.server.host, instance.port

    def remove_unused_plugins(self, files: ServerFiles, instance: Instance) -> None:
        unused = self.unused_plugin_paths(instance)
        plugins_dir = f"{self.server.game_dir}/addons/{AddonsBuilder.PLUGINS_DIR}"
        if removed := files.delete(plugins_dir, unused):
            console.item(f"removed unassigned plugins: {' '.join(removed)}")
