from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager

from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.config.inventory import Inventory
from deploy.config.secrets import ServerSecrets
from deploy.config.servers import Instance, Server
from deploy.errors import DeployError
from deploy.rcon import RconClient


class Deployer[S: Server](ABC):
    """Deploys and operates one inventory server."""

    def __init__(self, inventory: Inventory, server: S, *, dry_run: bool = False) -> None:
        self.inventory = inventory
        self.server = server
        self.secrets = ServerSecrets(server.id)
        self.dry_run = dry_run
        self.addons = AddonsBuilder(inventory, server, self.secrets)

    @abstractmethod
    def deploy(self) -> None:
        """Install the server's plugins and settings, then restart it."""

    @abstractmethod
    def restart(self) -> None:
        """Restart the server so it installs the latest CS2 build."""

    @abstractmethod
    def rcon_address(self, instance: Instance) -> AbstractContextManager[tuple[str, int]]:
        """The host and port this machine reaches the instance's RCON on, while the block runs."""

    def cleanup(self) -> None:
        raise DeployError(f"cleanup needs SSH; '{self.server.id}' is a {self.server.kind} server")

    def tunnel_database(self, local_port: int, db_host: str, db_port: int) -> None:
        raise DeployError(f"a tunnel needs SSH; '{self.server.id}' is a {self.server.kind} server")

    def print_plan(self, action: str, *details: str) -> None:
        """What `action` covers: each instance with its plugins, then the server kind's details."""
        console.section(f"{action} {self.server.id}")
        for instance in self.server.instances:
            plugins = " ".join(self.server.list_plugins(instance)) or "<none>"
            console.item(f"{instance.name} (port {instance.port}): {plugins}")
        for detail in details:
            console.item(detail)

    @contextmanager
    def rcon(self, instance_name: str | None) -> Generator[RconClient]:
        instance = self.server.instance(instance_name)
        password = self.secrets.require("RCON_PASSWORD")
        with (
            self.rcon_address(instance) as (host, port),
            RconClient(host, port, password) as client,
        ):
            yield client

    def unused_plugin_paths(self, instance: Instance) -> list[str]:
        """Plugin folder names the instance does not run."""
        return self.inventory.unused_plugins(self.server, instance)
