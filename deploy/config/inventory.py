from pathlib import Path
from typing import Annotated, Any, ClassVar, Self

import yaml
from pydantic import Field, ValidationError, field_validator, model_validator

from deploy.config.servers import DockerServer, Instance, Model, PanelServer, Server
from deploy.errors import DeployError
from deploy.paths import DEPLOY_DIR


class Plugin(Model):
    """A deployable plugin: its database, if any, and the settings production changes."""

    database: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class Database(Model):
    """Connection settings every database-backed plugin shares."""

    host: str | None = None
    port: int = 5432
    user: str = "postgres"
    ssl_mode: str = Field(default="prefer", alias="sslMode")


class Inventory(Model):
    PATH: ClassVar[Path] = DEPLOY_DIR / "inventory.yml"

    runtime_image: str
    database: Database = Field(default_factory=Database)
    plugins: dict[str, Plugin]
    servers: list[Annotated[DockerServer | PanelServer, Field(discriminator="kind")]]

    @classmethod
    def load(cls) -> Self:
        try:
            return cls.model_validate(yaml.safe_load(cls.PATH.read_text()))
        except ValidationError as error:
            raise DeployError(f"{cls.PATH.name} is invalid:\n{error}") from None

    @field_validator("runtime_image")
    @classmethod
    def check_untagged(cls, image: str) -> str:
        if ":" in image.rsplit("/", 1)[-1]:
            raise ValueError("must be the repository without a tag; each deploy picks the tag")
        return image

    @model_validator(mode="after")
    def check_servers(self) -> Self:
        ids = [server.id for server in self.servers]
        if len(ids) != len(set(ids)):
            raise ValueError("two servers share an id")
        for server in self.servers:
            for instance in server.instances:
                missing = [
                    name for name in server.list_plugins(instance) if name not in self.plugins
                ]
                if missing:
                    raise ValueError(f"server '{server.id}' uses undeclared plugins: {missing}")
        return self

    def server(self, server_id: str) -> DockerServer | PanelServer:
        for server in self.servers:
            if server.id == server_id:
                return server
        raise DeployError(f"server '{server_id}' not found in {self.PATH.name}")

    def targets(self, server_id: str | None) -> list[DockerServer | PanelServer]:
        """The named server, or every enabled one."""
        if server_id:
            return [self.server(server_id)]
        return [server for server in self.servers if server.enabled]

    def target(self, server_id: str | None) -> DockerServer | PanelServer:
        """The named server, or the only enabled one."""
        servers = self.targets(server_id)
        if len(servers) != 1:
            ids = ", ".join(server.id for server in servers) or "none enabled"
            raise DeployError(f"pass --server ({ids})")
        return servers[0]

    def unused_plugins(self, server: Server, instance: Instance) -> list[str]:
        """Inventory plugins the instance does not run, which a deploy removes from the server."""
        assigned = server.list_plugins(instance)
        return [name for name in self.plugins if name not in assigned]
