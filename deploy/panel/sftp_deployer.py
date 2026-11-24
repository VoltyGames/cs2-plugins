from deploy import console
from deploy.bundle.builder import AddonsBuilder
from deploy.config.servers import SftpServer
from deploy.panel.pterodactyl import PterodactylDeployer
from deploy.panel.sftp import SftpFiles
from deploy.paths import RENDER_DIR


class SftpDeployer(PterodactylDeployer[SftpServer]):
    """Uploads plugins over a panel node's SFTP, for panels that give no API key.

    Without the API it cannot stop or start the server, so the files load at its next restart.
    It leaves gameinfo.gi alone: these hosts keep their own, which already loads VoltMod.
    """

    def connect(self) -> SftpFiles:
        user = self.server.sftp_login(self.secrets.require("SFTP_USER"))
        return SftpFiles(self.server, user, self.secrets.require("SFTP_PASSWORD"))

    def deploy(self) -> None:
        instance = self.server.instance()
        game_dir = self.server.game_dir
        addons = self.addons.build(instance, RENDER_DIR / self.server.id)
        with self.connect() as files:
            self.print_plan(
                "Deploying",
                f"sftp:     {files.address}",
                f"host:     addons/{AddonsBuilder.HOST_ADDON_DIR}",
                "restart:  from the panel, after the upload",
            )
            if self.dry_run:
                console.done("Dry run complete; the server was not changed")
                return

            uploaded = files.upload_tree(addons, f"{game_dir}/addons")
            console.item(f"uploaded {uploaded} files")
            self.remove_unused_plugins(files, instance)
        console.done(f"Deploy to {self.server.id} complete")
        console.warn(f"{self.server.id} runs the old plugins until you restart it from the panel")

    def restart(self) -> None:
        # Not an error, so `deploy restart` across every server carries on past this one.
        console.section(f"Restarting {self.server.id}")
        console.warn(f"{self.server.id} has no panel API key; restart it from the panel")
