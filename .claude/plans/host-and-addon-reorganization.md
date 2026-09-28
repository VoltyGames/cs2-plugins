# Host and addon reorganization

Rename and simplify voltmod's host, move workshop addon downloads into one process-wide
`MultiAddonManager`, and give plugins one plain layout for their workshop content. Only this
repo consumes voltmod, so ABI and API names change freely (no aliases, no shims).

Decided:

- `IHost` and every host name may change. `HostAbiVersion` goes away (phase 1).
- Per-client addons (`Addons::RequireFor`) are deleted: nothing calls them.
- meatgg (3808651114) is the only addon. `meatgg_ui` (3801580041), `poe panorama-publish` and the
  separate `stronghold` addon are dead. Every checked-in `addonId` is 0; only
  `deploy/inventory.yml` sets the real id.

Workflow: one branch per repo (voltmod, stronghold, cs2-plugins), grouped commits per phase, no
release or relock until the end, one `/deploy-test` after the last phase.

## Phase 1: host names and cleanup (voltmod, no behaviour change)

Keep "Host" for the process-wide DLL and its root object only.

| Now | New |
| --- | --- |
| `src/Loader/` (server_valve shim) | `src/Bootstrap/` |
| `Loader/HookDispatcher` | `KHookForwarder` |
| `Loader/GameInfo.{hpp,cpp}` | `GameSearchPaths.{hpp,cpp}` |
| `Host/HostEntry.cpp`, class `HostEntry` | `Host/Host.{hpp,cpp}`, class `Host` |
| `Host/HostStart.hpp`, `HostStart` | `Host/LoaderHandoff.hpp`, `LoaderHandoff` |
| `Plugins/PluginHost` | `PluginRegistry` |
| `Plugins/HostView` | `PluginContext` |
| `HostState` | `SharedState` |
| `IHost`, `IHostEvents`, `IHostServices`, `IHostLanguages`, `IHostGameData` | `IPluginContext`, `IPluginEvents`, `IPluginServices`, `IPluginLanguages`, `IPluginGameData` |
| `Host/Loading/` + `Host/Plugins/` | one `Host/Plugins/` |
| `Loading/VoltCommand` | `Host/Console/VoltCommand` |
| `GameData/GameDataService` | `GameData` |
| `GameData/GameDataResolver`, `ResolvedEntry` | `GameDataScanner`, `GameDataEntry` |
| `GameData/ResolvedGameData`, `WriteResolvedGameData` | `GameDataRecord`, `WriteGameDataRecord` |
| `GameData/ModuleCache` | `ModuleSymbols` |
| `Schema/SchemaService` | `SchemaCheck` (verdict) + `SchemaDumper` (dump on server startup) |
| `Plugins/ServiceTable` | `PublishedInterfaces` |
| `EngineInterfaces.hpp` | `ResolveInterface.hpp` |
| `LoadedPlugin::Code` | `Library` |
| `Unreleased` | `LeakReport` |
| `CommandNames::RegisterForHost` | `Reserve` |
| `Discovered`, `LoadList::Allowed` | `InstalledScan`, `ToLoad` |

Versions and build stamps in the same phase (done 2026-09-28, uncommitted in voltmod; the entry
symbol is now `VoltMod_Plugin`):

- Delete `include/VoltMod/Host/Abi.hpp` and `HostAbiVersion`. `PluginDescriptor` carries the voltmod
  version the plugin was built with (`VOLTMOD_VERSION`, set by `conanfile.py`, passed into
  `cmake/PluginEntry.cpp.in` as it already is for the host); the loader refuses a plugin whose
  version differs from the host's: "built for voltmod 1.7.3, host is 1.7.4". The deploy ships
  host and plugins together, so an exact match costs nothing. Revisit only if third-party plugins
  built against older releases ever have to load.
- Build stamps: the host and every plugin carry the short commit SHA they were built from, with
  `-dirty` when the tree had uncommitted changes, because plugins change without a version bump.
  - Plugin: `voltmod_add_plugin` runs `git -C <plugin dir> describe --always --dirty --abbrev=7`
    on every build (a custom command that rewrites a generated header only when the value
    changed, so an unchanged stamp does not relink) and passes it to the descriptor as
    `BuildStamp`. Closed plugins are their own submodule repos, so `-C` picks the right history.
    No `.git` (a source tarball) gives `unknown`.
  - Host: the same stamp for the voltmod checkout. For a Conan package build, `conanfile.py`
    records the commit at export time and passes it as `VOLTMOD_COMMIT`.
  - Check the CI container (`build-linux`, `/deploy-test`) has each repo's `.git`, or pass the
    SHAs in as CMake variables there.
- Console:
  - `volt version` prints `VoltMod 1.7.4 (aad7c69)`.
  - `volt list` starts with the same line, then one plugin per line with its stamp:
    `stronghold v1.0.0 (2dfd824) - Build and defend a base`, `anticheat v1.2.0 (270fe88-dirty) - ...`.
  - Refused plugins keep their reason line.
  - The startup line "VoltMod host 1.7.4 loaded." gains the stamp.
- Docs: `docs/plugin.md` (descriptor, refusal reason), `docs/architecture.md:141` (was
  `HostAbiVersion`), the `volt` usage string and any doc listing `volt` verbs.

Cleanup in the same phase:

- Delete `HostView::PluginName()` (use `Name()`), `PluginHost::CommandOwner` and `Unreleased::Any`
  with the tests that only exist for them, `IHostServices::OnChanged` with `ServiceTable`'s changed
  event, and public `SharedLibrary::Close()`.
- Ready when built: `GameDataService::Resolve`, `SchemaService::Initialize` and
  `EngineHooks::Install/Uninstall` become constructors and destructors; `Host::Start` builds them
  in order.
- `GameDataService::Lookup` returns its failure reason by value, not a view into a member each
  call overwrites.
- Move `ValidateDescriptor` from `InstalledPlugins.cpp` into the plugin loader.
- Move the `SchemaCheck.cpp` free functions into their own header.
- `tools/lint` layering: make the include regex also match private `"Module/..."` includes, then
  either allow Host -> Schema or remove that include.
- Update `docs/architecture.md`, `voltmod/CLAUDE.md` module list, and every doc naming the old types.

## Phase 2: host responsibilities (voltmod)

- `Host/Files/ServerAssets.{hpp,cpp}`: owns `IFileSystem*` and the mounted folder per plugin;
  `Mount(name)` before a plugin's `Load`, `Unmount(name)` after `Unload`. Remove `_files`,
  `MountAssets`, `UnmountAssets` and `LoadedPlugin::Assets` from `PluginLoader`.
- Resolve engine interfaces once in `Host` (one struct) and pass it to EngineHooks, ServerAssets and
  SchemaCheck, instead of three separate `ResolveInterface` blocks.
- Drop `EngineHooks::_connected[]`; `DisconnectEveryone` reads `SharedState::Clients`.
- Consider moving the command-name calls off `IPluginContext` into `IPluginCommands`.

## Phase 3: MultiAddonManager (voltmod)

Today every plugin's `Runtime` builds its own `Addons` with its own `SendNetMessage` and
`ReplyConnection` hooks, chained, and main-menu, admin-system and stronghold each require meatgg.

- `Host/Workshop/MultiAddonManager`: built once by `Host` after GameData, fed by the host's
  connect/disconnect events. Moves `AddonDownloads` (as `DownloadQueue`) and both hooks out of
  `src/Workshop`. Uses `LazyHook` rather than hand-written install/remove. Download timeout and
  attempt limit become constants.
- `include/VoltMod/Host/IPluginAddons.hpp` (plain data only): `Add(addonId) -> token`,
  `Release(token)`, `MissingFor(slot, out, cap)`, `IsReady(slot)`, a ready callback. Reached via
  `IPluginContext::Addons()`. `PluginContext` records each plugin's tokens, releases them on
  unload and lists leaks in `LeakReport`.
- Plugin side: `runtime.AddonManager` (was `runtime.Addons`) wraps it:
  - `Subscription Add(uint64_t addonId)`; id 0 is a no-op, not an error.
  - `std::vector<uint64_t> MissingFor(int slot) const`, `bool IsReady(int slot) const`.
  - `Event<int> ClientReady` (was `Downloaded`).
  - `Status Available() const`.
  - Deleted: `RequireFor`, `Required`, `DownloadTimeoutSeconds`, `MaxDownloadAttempts`.
- Internal renames: `AddonAction::Mount` -> `KeepMounted`, `ToMount` -> `ClientMountList`,
  `Bindings::ServerAddons` -> `ServerAddonList`; the id parameter is `addonId` everywhere
  (including `Map::ChangeToWorkshop`).
- `UsePanorama(layout)` drops its id; `PanoramaMenu::CanShow` keeps asking `IsReady(slot)`.
  `PanoramaMenuSettings` keeps only `panorama`.
- Docs: rewrite `docs/workshop.md` around the manager and `server-assets` (it still says the
  server mounts nothing); update `docs/menu.md`, `docs/panorama.md`, `docs/plugin.md`, the
  gamedata docs; CHANGELOG entries for `server-assets` and this phase.

## Phase 4: plugins

- Every plugin: one top-level `addonId` setting, default 0, required once in `App`:
  `_subs.Add(Runtime.AddonManager.Add(Config.Get().addonId))`. Remove `menu.addonId` from
  main-menu and admin-system; `UsePanorama(layout)`. Delete stronghold's `App::RequireAddon`.
- `deploy/inventory.yml`: `addonId` 3808651114 per instance for the three plugins, under the
  new key.
- stronghold:
  - `addon/` -> `content/`; `panorama/` moves under it.
  - `src/Assets/Addon.hpp` -> `src/Assets/Resources.hpp` (it holds model, sound and animation names).
  - Delete the orphaned particles in `server-assets` (40 `.vpcf_c` and the fx materials with no
    source in the repo, none referenced by `Catalog.cpp`), or bring their sources in if they are
    wanted.
  - README: replace "Publishing the addon" with the meatgg flow; fix `docs/assets.md` (junction
    claim, table rows).
- main-menu: move the brand kit `panorama/templates/meatgg` to `workshop/meatgg/templates`; fix the
  README (`menu.addonId`, 3801580041, meatgg_ui).
- admin-system: `docs/admin-system.md` publish section -> meatgg.

## Phase 5: tooling and templates

- Delete `poe panorama-publish`, `plugins/stronghold/scripts/assets.ps1`, and every `meatgg_ui`
  mention.
- `voltmod content compile|install|remove <plugin> [folder]` in the voltmod CLI, replacing
  `.claude/skills/3d-model/scripts/compile.py` and `assets.ps1`; the 3d-model skill calls it.
- `poe bootstrap` links `content/csgo_addons/<plugin>` to the plugin's `content/` (junction), so
  the Workshop Tools read the repo directly.
- `ServerAssets.export` and `workshop/build_meatgg.py` copy only compiled files whose source exists
  in the plugin's `content/`, so no orphan ships.
- `build_meatgg.py`: add the skillgroups line to the client's own `gameinfo.gi` when missing
  (UTF-8, no BOM) instead of keeping a patched copy in `workshop/gameinfo.gi`; bring the rank-icon
  sources into `workshop/meatgg/`.
- `voltmod new plugin <name> --content`: adds `content/panorama/screens/`, `addonId: 0` and the
  `AddonManager.Add` call. Without the flag the scaffold is unchanged.
- Docs: `docs/getting-started-plugin.md` ("where to put models, sounds and screens"),
  `.claude/rules/framework-patterns.md` (`UsePanorama(layout)`, `AddonManager`), CLAUDE.md commands
  and layout, the 3d-model and build-local skills.

## Checks

- `uv run poe test`, `uv run poe lint`, and `uv run poe test` inside `voltmod` after each phase.
- Local server: plugins load, `volt list` clean, no leak report on `volt reload`.
- Client: with `addonId` 3808651114 a fresh client downloads meatgg once (not once per plugin),
  the menus draw in Panorama, and the launchers show in first person.
- `/deploy-test` once after phase 5.
