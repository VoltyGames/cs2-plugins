import shlex
import subprocess
import textwrap
from pathlib import PurePosixPath

from deploy import console
from deploy.config.servers import DockerServer, Instance
from deploy.docker.ssh import Ssh
from deploy.errors import DeployError


class DockerHost:
    """Runs one host's instances, each its own Compose project, and cleanup commands over SSH."""

    # A first start downloads the whole game.
    STEAMCMD_TIMEOUT_MINUTES = 90
    STEAMCMD_TIMEOUT_EXIT_CODE = 3

    def __init__(self, server: DockerServer, ssh: Ssh) -> None:
        self._server = server
        self._ssh = ssh
        self._root = shlex.quote(server.deploy_root)

    def create_folders(self, paths: list[str]) -> None:
        self._ssh.run(f"mkdir -p {shlex.join(paths)}")

    def remove(self, paths: list[str]) -> None:
        if paths:
            self._ssh.run(f"rm -rf -- {shlex.join(paths)}")

    def pull(self) -> None:
        # Every instance runs the same image.
        self._compose(self._server.instances[0], "pull")

    def recreate(self, instance: Instance) -> None:
        """Start the instance in a new container even when nothing changed, so pre.sh runs."""
        self._compose(instance, "up -d --force-recreate")
        self._await_steamcmd(instance)

    def restart(self, instance: Instance) -> None:
        self._compose(instance, "restart")
        self._await_steamcmd(instance)

    def check_running(self) -> None:
        # One query for every instance: each Compose project would be its own SSH round trip.
        query = "docker ps --filter status=running --format '{{.Names}}'"
        running = self._ssh.run(query, capture=True).split()
        stopped = [
            item
            for item in self._server.instances
            if self._server.container_name(item) not in running
        ]

        if not stopped:
            console.item("every instance is running")
            return

        names = ", ".join(item.name for item in stopped)
        console.error(f"{names} not running; the last log lines of each follow")
        logs = (self._compose_command(item, "logs --tail=80") for item in stopped)
        self._ssh.run("; ".join(f"({item}) || true" for item in logs))
        raise DeployError(f"{names} did not start on {self._server.id}")

    def remove_old_images(self, repository: str, keep: str) -> None:
        """Remove the repository's tags other than keep, since every deploy adds a tag."""
        image_format = "'{{.Repository}}:{{.Tag}}'"
        tags = f"docker image ls {shlex.quote(repository)} --format {image_format}"
        old_tags = f"{tags} | grep -vxF {shlex.quote(keep)} | xargs -r docker image rm"
        self._ssh.run(f"{old_tags} 2>/dev/null; docker image prune -f")

    def remove_deployment(self, repository: str) -> None:
        """Delete the stack, its containers and images, deploy_root and cs2_root."""
        folders = [self._server.deploy_root, self._server.cs2_root]
        for path in folders:
            posix = PurePosixPath(path)
            if not posix.is_absolute() or ".." in posix.parts or len(posix.parts) < 4:
                raise DeployError(f"refusing to delete {path}; use a deeper absolute path")

        names = [self._server.container_name(item) for item in self._server.instances]
        images = f"docker image ls -q {shlex.quote(repository)} | xargs -r docker image rm -f"
        downs = (self._compose_command(item, "down") for item in self._server.instances)

        commands = [
            *(f"({down}) || true" for down in downs),
            f"docker rm -f {shlex.join(names)} 2>/dev/null || true",
            f"{images} 2>/dev/null || true",
            f"rm -rf -- {shlex.join(folders)}",
        ]
        self._ssh.run("; ".join(commands))

    def _compose(self, instance: Instance, arguments: str, *, capture: bool = False) -> str:
        return self._ssh.run(self._compose_command(instance, arguments), capture=capture)

    def _compose_command(self, instance: Instance, arguments: str) -> str:
        """docker-compose.yml describes one instance; its .env and project name pick which."""
        project = shlex.quote(f"cs2-{instance.name}")
        env_file = shlex.quote(f"instances/{instance.name}/.env")
        compose = f"docker compose -p {project} --env-file {env_file}"
        return f"cd {self._root} && {compose} {arguments}"

    def _await_steamcmd(self, instance: Instance) -> None:
        """Block while SteamCMD runs in the instance's container, so updates go one at a time."""
        waiting = shlex.quote(f"    {instance.name}: SteamCMD still running")
        limit = self.STEAMCMD_TIMEOUT_MINUTES * 60
        script = textwrap.dedent(f"""\
            container=$({self._compose_command(instance, "ps -q")}) || exit $?
            [ -n "$container" ] || exit 0
            sleep 10
            waited=0
            while docker exec "$container" sh -lc 'pgrep -f steamcmd >/dev/null 2>&1'; do
                [ $waited -lt {limit} ] || exit {self.STEAMCMD_TIMEOUT_EXIT_CODE}
                echo {waiting}
                sleep 15
                waited=$((waited + 15))
            done
        """)

        try:
            self._ssh.run(script)
        except subprocess.CalledProcessError as error:
            if error.returncode != self.STEAMCMD_TIMEOUT_EXIT_CODE:
                raise
            minutes = self.STEAMCMD_TIMEOUT_MINUTES
            raise DeployError(f"SteamCMD in {instance.name} ran over {minutes} minutes") from None
