import shlex
from pathlib import Path

from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.config.secrets import ServerSecrets
from deploy.config.servers import DockerServer, Instance
from deploy.paths import FILES_DIR


class ComposeProject:
    """docker-compose.yml plus each instance's plugin bundle, env file and pre-launch hook."""

    COMPOSE_FILE = FILES_DIR / "docker" / "docker-compose.yml"
    PRE_LAUNCH_HOOK = FILES_DIR / "docker" / "pre.sh"

    def __init__(
        self, server: DockerServer, secrets: ServerSecrets, addons: AddonsBuilder, image: str
    ) -> None:
        self._server = server
        self._secrets = secrets
        self._addons = addons
        self._image = image

    def render(self, destination: Path) -> None:
        hook_text = self.PRE_LAUNCH_HOOK.read_text()
        for instance in self._server.instances:
            instance_dir = destination / "instances" / instance.name
            self._addons.build(instance, instance_dir / "bundles")
            self._write(instance_dir / ".env", self._env_file(instance))
            hook = instance_dir / "pre.sh"
            self._write(hook, hook_text)
            hook.chmod(0o755)
        compose_text = self.COMPOSE_FILE.read_text()
        self._write(destination / self.COMPOSE_FILE.name, compose_text)

    @staticmethod
    def _write(path: Path, text: str) -> None:
        """The host reads these files, so they keep LF endings whatever the renderer runs on."""
        path.write_text(text, newline="\n")

    def _env_file(self, instance: Instance) -> str:
        token = self._secrets.get(f"GSLT_{instance.name}")
        if not token:
            console.warn(f"GSLT_{instance.name} is not set; '{instance.name}' starts in LAN mode")
        values = {
            # Read by docker-compose.yml; the rest configures the container.
            "INSTANCE": instance.name,
            "CONTAINER_NAME": self._server.container_name(instance),
            "RUNTIME_IMAGE": self._image,
            "GAME_INSTALL": self._server.game_install,
            "SRCDS_TOKEN": token,
            "CS2_RCONPW": self._secrets.get("RCON_PASSWORD"),
            "CS2_PORT": str(instance.port),
            "CS2_STARTMAP": instance.map,
            "CS2_SERVERNAME": instance.server_name,
        }
        # No +exec server.cfg here: it can turn VAC back on after -insecure.
        if instance.insecure:
            values["CS2_ADDITIONAL_ARGS"] = "-insecure"
        # Quoted: Compose expands an unquoted $ when it interpolates the file.
        return "".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items())
