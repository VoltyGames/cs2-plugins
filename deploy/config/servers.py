import re
from typing import ClassVar, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from deploy.errors import DeployError


class Model(BaseModel):
    # A misspelled inventory key fails the load instead of being ignored.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Instance(Model):
    """One CS2 server process with its own port, map and plugin set."""

    name: str
    port: int
    hostname: str | None = None
    map: str = "de_dust2"
    insecure: bool = False
    plugins: list[str] | None = None

    @property
    def server_name(self) -> str:
        return self.hostname or f"CS2 {self.name}"


class Server(Model):
    """What every server kind has: an id, its plugins and its instances."""

    id: str
    kind: str
    host: str
    environment: str | None = None
    # The deploy/secrets folder to read; servers on one panel account can share one.
    secrets: str | None = None
    enabled: bool = True
    plugins: list[str] = Field(default_factory=list)
    instances: list[Instance] = Field(min_length=1)

    @model_validator(mode="after")
    def check_instances_unique(self) -> Self:
        for field in ("name", "port"):
            values = [getattr(instance, field) for instance in self.instances]
            if len(values) != len(set(values)):
                raise ValueError(f"server '{self.id}' has two instances with the same {field}")
        return self

    @property
    def secrets_name(self) -> str:
        return self.secrets or self.id

    def list_plugins(self, instance: Instance) -> list[str]:
        """The instance's own list replaces the server's; it does not extend it."""
        return self.plugins if instance.plugins is None else instance.plugins

    def instance(self, name: str | None = None) -> Instance:
        """The named instance, or the only one."""
        if name is None:
            if len(self.instances) > 1:
                raise DeployError(f"server '{self.id}' has several instances; pass --instance")
            return self.instances[0]
        for instance in self.instances:
            if instance.name == name:
                return instance
        raise DeployError(f"instance '{name}' not found on server '{self.id}'")


class DockerServer(Server):
    """A Linux host reached over SSH, running one container per instance."""

    kind: Literal["docker"]
    ssh_user: str = "steam"
    ssh_port: int = 22
    cs2_root: str = "/home/steam/cs2"
    deploy_root: str = "/home/steam/cs2/deploy"

    @property
    def game_install(self) -> str:
        """The SteamCMD install every instance on the host shares."""
        return f"{self.cs2_root.rstrip('/')}/server"

    def instance_dir(self, instance: Instance) -> str:
        return f"{self.deploy_root}/instances/{instance.name}"

    def container_name(self, instance: Instance) -> str:
        return f"{self.id}-cs2-{instance.name}"


class PterodactylServer(Server):
    """A Pterodactyl panel server: one CS2 process whose files sit under the container root."""

    game_dir: str = "/game/csgo"
    instances: list[Instance] = Field(min_length=1, max_length=1)

    @field_validator("game_dir")
    @classmethod
    def strip_trailing_slash(cls, path: str) -> str:
        return path.rstrip("/")


class PanelServer(PterodactylServer):
    """A Pterodactyl panel server, deployed through the panel's client API."""

    PAGE_URL: ClassVar[re.Pattern[str]] = re.compile(r"https?://[^/]+/server/[^/]+/?")

    kind: Literal["panel"]
    panel_url: str

    @field_validator("panel_url")
    @classmethod
    def check_panel_url(cls, url: str) -> str:
        if not cls.PAGE_URL.fullmatch(url):
            raise ValueError(
                "must be the server's panel page, like https://panel.example.com/server/abc12345"
            )
        return url

    @property
    def api_url(self) -> str:
        url = urlsplit(self.panel_url)
        server = url.path.rstrip("/").rsplit("/", 1)[1]
        return f"{url.scheme}://{url.netloc}/api/client/servers/{server}"


class SftpServer(PterodactylServer):
    """A Pterodactyl panel server with no API key, deployed over its node's SFTP.

    Its id is the panel's server id, which the SFTP login ends with.
    """

    kind: Literal["sftp"]
    # The node's address, when it differs from the game host.
    sftp_host: str | None = None
    sftp_port: int = 2022

    @property
    def sftp_address(self) -> str:
        return self.sftp_host or self.host

    def sftp_login(self, user: str) -> str:
        """Pterodactyl's `<panel user>.<server id>`; a user that has the id already stays."""
        return user if "." in user else f"{user}.{self.id}"
