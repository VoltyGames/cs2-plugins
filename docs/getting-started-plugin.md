# Create your first plugin

From a working checkout to a plugin answering `!ping`. Set the repository up first with
[Local development](local-development.md).

```powershell
uv run poe new-plugin hello-world
uv run poe run hello-world
```

Then, in the server console, `volt list` should show `hello-world` with its version. Join and type
`!ping`; the translated reply proves the plugin loaded, command routing works, and its translation
file was installed.

## What the scaffold writes

Plugin names are kebab case. `new-plugin` creates the directory and adds
`add_subdirectory(plugins/hello-world)` to the root `CMakeLists.txt`, so there is nothing to edit
by hand.

```text
plugins/hello-world/
  CMakeLists.txt        voltmod_add_plugin(hello-world)
  plugin.json           name, version, logTag, description, author, dependencies
  README.md             what the plugin does, its commands and settings
  configs/
    settings.jsonc      addonId 0, menu.panorama false
  translations/
    en.json
  src/
    App.cpp             App::Load: requires the addon, draws menus on the layout, registers commands
    App.hpp             HelloWorld::App: everything the plugin owns for one load cycle
    Commands.cpp        the !ping command
    Config.hpp          the settings struct
  panorama/screens/
    hello_world_menu.xml.j2, .css.j2   the menu layout; the build renders Ui/HelloWorldMenu.hpp
  content/              workshop sources (models, particles, sounds) for the CS2 Workshop Tools
```

`plugin.json` is the plugin's identity. `name` must equal the directory and the CMake target, CMake
reads the name and version from it, and the host reads the installed copy to decide what may load.
An unknown key is an error. A `dependencies` entry refuses this plugin when the other one is not
there; load order is alphabetical either way.

## Where to put things

| Change | File |
| --- | --- |
| Startup and composition | `src/App.hpp` (members, in dependency order) and `src/App.cpp` (`Load`) |
| Commands | `src/Commands.cpp`, or another `.cpp` under `src/` |
| Settings | `src/Config.hpp`, plus `configs/settings.jsonc` |
| Player-facing text | every file under `translations/` |
| SDK-free logic | plain C++ types, so it can be unit-tested |

`voltmod_add_plugin` discovers every `.cpp` under `src/`, so a new file needs no CMake edit.
`DATABASE` adds PostgreSQL, MariaDB and SQLite.

A third-party C++ dependency takes three steps: a requirement in `conanfile.py`, `find_package` in
the root `CMakeLists.txt`, and the imported target in the plugin's own CMake.

## Talking to another plugin

An interface two plugins share lives in `contracts/include/`, not in either plugin. The
provider publishes it and the consumer asks for it:

```cpp
_published = runtime.Exchange.Publish<IThing>(&_impl);  // provider, in App::Load; keep the Subscription
auto* thing = runtime.Exchange.Get<IThing>();            // consumer; null when the provider is not loaded
```

Ask for it where you use it rather than caching the pointer: the publisher can unload between
callbacks. List the provider under `optionalDependencies` in `plugin.json` so the host loads it
first when it is installed. Never pass ownership or let an exception cross the module boundary.

## The loop

```powershell
uv run poe build
uv run poe install hello-world
```

Restart the local server when Windows keeps the replaced DLL locked. Before pushing:

```powershell
uv run poe lint
uv run poe format
uv run poe test
```

## Framework documentation

Everything that is not specific to this repository lives in the framework's docs:

| Page | Covers |
| --- | --- |
| [Getting started](https://github.com/voltygg/voltmod/blob/main/docs/getting-started.md) | the plugin shape, first command, first build |
| [Plugin](https://github.com/voltygg/voltmod/blob/main/docs/plugin.md) | the load cycle, `App`, hooks, game events |
| [Config](https://github.com/voltygg/voltmod/blob/main/docs/config.md) | settings, schemas, translations |
| [Commands](https://github.com/voltygg/voltmod/blob/main/docs/commands.md) | registration, permissions, targeting |
| [SDK wrappers](https://github.com/voltygg/voltmod/blob/main/docs/sdk.md) | entities, events, hooks, messaging |
| [Testing](https://github.com/voltygg/voltmod/blob/main/docs/testing.md) | the SDK-free test suite |

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `hello-world` is missing from `volt list` | `game/csgo/addons/voltmod/plugins/hello-world/plugin.json` and `hello-world.dll` |
| The plugin loads but `!ping` does nothing | `translations/en.json` was installed, and `plugin.locale` names a file that exists |
| `settings.jsonc` changes are ignored | The installer seeds it once; edit the copy under `game/csgo/addons/voltmod/plugins/hello-world/configs/` |
| Conan cannot resolve SDK packages | `uv run poe bootstrap`. A missing published binary is a publication problem; changing source will not fix it |
