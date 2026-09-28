# CS2 plugins

C++23 server plugins for Counter-Strike 2 on the VoltMod framework
(Conan package `voltmod/[~1.7]`).

- `voltmod` is a separate Git repo with its own `CLAUDE.md`. Check its status and diffs separately.
- `references/` is read-only.

## Comments and names

MUST:

- Comment only where the code cannot say it: intent, ownership, lifetime, threading, compatibility.
- One line inside a function. A public contract may take a few lines of Doxygen. No essays.
- Names are plain words a new developer understands. If a name needs a comment to decode it, rename it.

## Commands

```bash
uv run poe doctor                            # check toolchain, Conan, optional CS2 server
uv run poe bootstrap                         # first-time: install VoltMod profiles and remote
uv run poe build                             # compile (windows-msvc-release)
uv run poe test                              # compile, then CTest
uv run poe lint                              # ruff + source conventions + panorama and schema checks
uv run poe schema                            # regenerate the admin-system table specs from its migrations
uv run poe run <plugin>                      # build, copy to CS2_SERVER_PATH and launch
uv run poe install                           # copy every built plugin; name one to copy only it
uv run poe panorama                          # render, compile and install the Panorama screens into your client (Windows)
uv run poe meatgg-addon                      # build the meatgg workshop addon: every screen, Stronghold content, rank icons
uv run poe new-plugin <name>
```

Output: `build/<preset>/plugins/<name>/<platform-arch>/`. Compiling needs an MSVC dev
shell; see the `/build-local` skill. `build-linux` only works in the CI container.

Framework and plugin together:

```bash
uv run conan editable add voltmod   # once
uv run poe build                           # checkout first, then plugins
uv run poe build --relock                  # before committing; commit conan.lock with the change
```

## Layout

```text
plugins/admin-system/  Admins, punishments, menus, reports, Postgres/MariaDB/SQLite
plugins/anticheat/     Detection cores, engine adapters, responses
plugins/bhop/          Bunnyhop modes
plugins/main-menu/     !menu hub; owns the meat.gg Panorama brand kit (panorama/templates/meatgg)
contracts/             Interfaces shared between plugins (header-only, not a plugin)
deploy/                Deploy CLI for panel servers and Docker hosts
workshop/              Builds the meatgg workshop addon; meatgg/ holds compiled files copied in as they are
tools/                 Standalone builds outside the root CMake; legacy-dummy/ stands in for a legacy Metamod plugin
docs/                  Development and deployment notes
```

A plugin owns `plugin.json` (name, version, log tag, dependencies), `src/`, `tests/`, `configs/`
(operator-owned, seeded once), `translations/` (and `migrations/`, `data/`, `server-assets/` when it ships them), and a `CMakeLists.txt` calling `voltmod_add_plugin(<name>)`; register it with
`add_subdirectory()` in the root. C++ deps: `conanfile.py`, then `find_package` in the root CMake, then link in the plugin.

Conventions and framework patterns are in `.claude/rules/` and load per file path.
