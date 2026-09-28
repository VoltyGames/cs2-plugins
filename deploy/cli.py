"""Deploy CS2 plugin servers: panel servers over the panel API, Docker hosts over SSH.

Run from the repository root: uv run poe deploy <command>
"""

import json
import shlex
import subprocess
import sys
from typing import Annotated, Any

import typer

from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.bundle.packager import AddonPackager
from deploy.config.inventory import Inventory
from deploy.deployer import Deployer
from deploy.docker.deployer import DockerDeployer
from deploy.errors import DeployError
from deploy.panel.deployer import PanelDeployer

app = typer.Typer(help=__doc__, no_args_is_help=True, pretty_exceptions_enable=False)

ServerOption = Annotated[
    str | None, typer.Option("--server", help="Server id; default: every enabled server")
]
DryRunOption = Annotated[bool, typer.Option("--dry-run", help="Show changes without making them")]
PluginsArgument = Annotated[
    list[str] | None, typer.Argument(help="Plugins to package; default: every inventory plugin")
]

DEPLOYERS: dict[str, type[Deployer[Any]]] = {"docker": DockerDeployer, "panel": PanelDeployer}


def deployers_for(server_id: str | None, dry_run: bool = False) -> list[Deployer[Any]]:
    """Deployers for the named server, or for every enabled one."""
    inventory = Inventory.load()
    return [
        DEPLOYERS[server.kind](inventory, server, dry_run=dry_run)
        for server in inventory.targets(server_id)
    ]


def deployer_for(server_id: str | None, dry_run: bool = False) -> Deployer[Any]:
    """The named server's deployer, or the only enabled server's."""
    inventory = Inventory.load()
    server = inventory.target(server_id)
    return DEPLOYERS[server.kind](inventory, server, dry_run=dry_run)


@app.command("ci-matrix")
def ci_matrix(server: ServerOption = None) -> None:
    """Print what a deploy covers, as GitHub output lines."""
    inventory = Inventory.load()
    servers = inventory.targets(server)
    matrix = [{"id": item.id, "environment": item.environment} for item in servers]
    print(f"servers={json.dumps(matrix, separators=(',', ':'))}")
    print(f"docker={'true' if any(item.kind == 'docker' for item in servers) else 'false'}")
    print(f"runtime_image={inventory.runtime_image}")


@app.command()
def package(plugins: PluginsArgument = None) -> None:
    """Stage the Linux build of the host and each plugin under build/package/."""
    packager = AddonPackager()
    # The host goes in every package set; a plugin only loads under the host it was built with.
    packager.package(AddonsBuilder.HOST)
    for plugin in plugins or Inventory.load().plugins:
        packager.package(plugin)


@app.command()
def push(server: ServerOption = None, dry_run: DryRunOption = False) -> None:
    """Install plugins and settings, then restart the servers."""
    for deployer in deployers_for(server, dry_run):
        deployer.deploy()


@app.command()
def restart(server: ServerOption = None, dry_run: DryRunOption = False) -> None:
    """Restart servers so they install the latest CS2 build."""
    for deployer in deployers_for(server, dry_run):
        deployer.restart()


@app.command()
def cleanup(
    server: Annotated[str, typer.Argument(help="The Docker host's server id")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Confirm the deletion")] = False,
    dry_run: DryRunOption = False,
) -> None:
    """Remove a Docker host's containers, deploy files, CS2 install and runtime images."""
    if not yes and not dry_run:
        raise DeployError("cleanup deletes the server's files; pass --yes, or --dry-run to preview")
    deployer_for(server, dry_run).cleanup()


@app.command()
def rcon(
    commands: Annotated[list[str], typer.Argument(help="Console commands, each quoted")],
    server: ServerOption = None,
    instance: Annotated[
        str | None, typer.Option("--instance", help="Default: the server's only instance")
    ] = None,
) -> None:
    """Run console commands on a live instance."""
    with deployer_for(server).rcon(instance) as client:
        for command in commands:
            console.section(command)
            if response := client.execute(command):
                console.info(response)


@app.command()
def tunnel(
    server: ServerOption = None,
    local_port: Annotated[
        int, typer.Option("--local-port", help="The port on this machine")
    ] = 5433,
    db_host: Annotated[str, typer.Option("--db-host", help="As seen from the host")] = "localhost",
    db_port: Annotated[int, typer.Option("--db-port", help="As seen from the host")] = 5432,
) -> None:
    """Forward a local port to a Docker host's database until Ctrl-C."""
    deployer_for(server).tunnel_database(local_port, db_host, db_port)


def main() -> None:
    try:
        app()
    except DeployError as error:
        console.error(str(error))
        sys.exit(1)
    except subprocess.CalledProcessError as error:
        console.error(f"`{shlex.join(error.cmd)}` exited with code {error.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
