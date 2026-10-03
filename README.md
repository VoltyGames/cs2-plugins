# CS2 plugins

[![CI](https://github.com/voltygg/cs2-plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/voltygg/cs2-plugins/actions/workflows/ci.yml)
[![C++23](https://img.shields.io/badge/C%2B%2B-23-00599C?logo=cplusplus)](https://en.cppreference.com/w/cpp/23)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Native C++23 plugins for Counter-Strike 2 dedicated servers, built on
[VoltMod](https://github.com/voltygg/voltmod).

<p align="center">
  <img src="docs/assets/meatgg-ui-workshop-preview.png" alt="Preview of the meat.gg Panorama menu interface" width="720">
</p>

## Plugins

| Plugin | Purpose | Requirements |
| --- | --- | --- |
| [admin-system](plugins/admin-system/README.md) | Admins, punishments, player controls, menus, reports, and multi-server permissions | Uses PostgreSQL, MariaDB, or bundled SQLite |
| [anticheat](https://github.com/voltygg/cs2-anticheat) | Server-side aim analysis and client-integrity checks | Can use admin-system for alerts and bans; detection also works alone |
| [bhop](plugins/bhop/README.md) | Smooth, client-predicted bunnyhop with per-player grants | Admin-system is needed only for grants mode |
| [deathmatch](plugins/deathmatch/README.md) | Valve's free-for-all deathmatch with random spawns away from live players and no bonus rounds | Start the server with `+game_type 1 +game_mode 2` |
| [main-menu](plugins/main-menu/) | A configurable `!menu` hub for stats, VIP, admin tools, and website links | Supports Panorama UI with a center-HTML fallback |
| [stronghold](https://github.com/voltygg/cs2-stronghold) | Build-and-defend team deathmatch: instant respawn, an economy, and buildable structures guarding each team's Core | In development |

Shared interfaces between plugins live in `contracts/`.

## Install a release

You need a Counter-Strike 2 dedicated server. Metamod:Source is optional.

1. Download the plugin archive from the repository's
   [releases](https://github.com/voltygg/cs2-plugins/releases).
2. Extract it into the server's `game/csgo` directory. The archive includes the VoltMod host and
   the selected plugin.
3. In `game/csgo/gameinfo.gi`, add `Game csgo/addons/voltmod` directly above `Game csgo`. A CS2
   update removes this line; add it again after one.
4. Edit `game/csgo/addons/voltmod/plugins/<plugin>/configs/settings.jsonc`.
5. Restart the server.
6. Run `volt list` in the server console and confirm that the plugin is loaded.

The anticheat starts in `observe` mode; read its guide before changing the rollout mode.

## Build from source

Local Windows development requires Git, [uv](https://docs.astral.sh/uv/), Python 3.14 or newer,
Visual Studio 2022 or newer with the C++ workload, and a local CS2 dedicated server.

```powershell
git clone https://github.com/voltygg/cs2-plugins.git
cd cs2-plugins
Copy-Item .env.example .env      # set CS2_SERVER_PATH in .env
uv sync
uv run poe doctor
uv run poe bootstrap             # first-time Conan setup, build, and tests
uv run poe run admin-system
```

The last command builds and installs `admin-system`, then starts the server. Output goes to
`build/<preset>/plugins/<name>/<platform-arch>/`. Installation does not overwrite an existing
`settings.jsonc`.

### Common development commands

| Command | Purpose |
| --- | --- |
| `uv run poe doctor` | Check the toolchain, project files, Conan setup, and local CS2 server |
| `uv run poe bootstrap` | Perform first-time setup, then configure, build, and test |
| `uv run poe build [-p preset]` | Build with a `windows-msvc-{release,debug}` or `linux-steamrt-{release,debug}` preset |
| `uv run poe build-linux` | Build the Linux Steam Runtime preset inside the CI container |
| `uv run poe run [name]` | Build, install into the local server, and start it |
| `uv run poe install [name]` | Install a built plugin without starting the server |
| `uv run poe serve` | Start the configured local server |
| `uv run poe test` | Build and run the CTest suite |
| `uv run poe lint` / `uv run poe format` | Check project conventions or format the C++ source |
| `uv run poe schema` | Regenerate admin-system table specifications from its migrations |
| `uv run poe new-plugin <name>` | Create and register a new plugin |
| `uv run poe panorama` | Compile Panorama screens into the local CS2 client on Windows |
| `uv run poe deploy <command>` / `uv run poe rcon` | Deploy to remote hosts or send an RCON command |

## Documentation

| Guide | Topic |
| --- | --- |
| [Create your first plugin](docs/getting-started-plugin.md) | Scaffold, build, install, and verify a plugin |
| [Local development](docs/local-development.md) | Configure the toolchain, presets, local server, or editable VoltMod checkout |
| [Admin system](docs/admin-system.md) | Configure permissions, databases, and a multi-server installation |
| [Deployment](deploy/README.md) | Package and deploy to panel servers or Docker hosts |
| [Contributing](CONTRIBUTING.md) | Follow the repository's development and review conventions |
| [VoltMod documentation](https://voltygg.github.io/voltmod/) | Learn the framework APIs and host model |

## Repository layout

```text
plugins/     plugin source, configuration, tests, and plugin guides
docs/        operator and contributor guides
deploy/      deployment CLI, inventory, and host tooling
voltmod/     optional VoltMod checkout for coordinated framework changes
build/       generated build output
```

`voltmod` is a separate Git repository used for changes that touch both VoltMod and a
plugin. Normal plugin builds get VoltMod from Conan.
