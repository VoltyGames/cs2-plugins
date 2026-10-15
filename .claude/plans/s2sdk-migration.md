# Migrate from hl2sdk-cs2 to s2sdk

## Goal

VoltMod and the plugins build against `alliedmodders/s2sdk` (branch `cs2`) instead of
`alliedmodders/hl2sdk` (branch `cs2`). The `hl2sdk-cs2` package is deleted, and the framework uses the
SDK's own declarations where it reads raw gamedata offsets or defines its own copies today.

Rules for this change:

- No fallbacks or shims. No forwarding headers under the old paths (`eiface.h`, `tier1/convar.h`, ...),
  no `using` aliases for old names, no `hl2sdk_*` CMake function aliases, no `hl2sdk-cs2` package alias,
  no "use the SDK accessor, else the gamedata offset" branches. Old code and old gamedata keys are deleted
  in the same change that replaces them.
- Breaking changes are fine; voltmod has no external consumers. Plugins in this repo (including the
  Stronghold submodule) are updated in the same branch.
- Fix what the compiler points at; don't paper over a removed SDK API.
- Work on a new branch per repo, grouped commits, no release or relock, then test on the local server.

## Facts this plan relies on

Checked on 2026-10-14 against `references/s2sdk` (tip `809a2d48`, 2026-10-13).

1. **hl2sdk `cs2` is frozen.** Its last commit is `3f4110dc` "Add branch move notice" (2026-10-07), which
   is exactly voltmod's pin in `conan/recipes/hl2sdk-cs2/conandata.yml`. The daily `watch.yml` bump will
   never find a newer commit. All CS2 SDK work now lands in s2sdk.
2. **Same history.** s2sdk contains hl2sdk's history unchanged; `3ea5305b` (the commit before the move
   notice) has the same hash in both. The notice commit exists only on hl2sdk. 489 commits sit between
   `3ea5305b` and the s2sdk tip.
3. **Line endings were normalized** in `2d68a8d0`, which inflates diff stats (about 133k changed lines).
   Compare with `--ignore-cr-at-eol` or by file renames, not raw stats.
4. **s2sdk forbids compatibility wrappers** (its `AGENTS.md`): removed APIs are deleted, not aliased.
   Every bump can break our build on purpose, so pin one commit and bump deliberately.
5. **s2sdk's CMake builds only the libraries** (`interfaces`, `mathlib`, `libprotobuf`), with `/MT` on
   MSVC. It describes nothing for consumers; include dirs, defines and libs still come from our recipe.
   The prebuilt `lib/` binaries are still shipped and keep the same names and folders.
6. **`GameEntitySystem()` is declared, not defined.** `game/shared/gameentitysystem.h` has
   `extern CGameEntitySystem* GameEntitySystem();`; `IGameResourceService` has no accessor for it. The
   `GameEntitySystem` gamedata offset stays.
7. **Not declared in s2sdk:** `CNetworkGameServer::m_szAddons`, `CNetworkGameServer::ReplyConnection`,
   `CUserCmd` offsets, `g_GameEventManager`, `GetLegacyGameEventListener`, `AddEntityIOEvent`, and every
   game-DLL function or vtable (pawn, controller, item and weapon services, custom HUD). These stay in
   gamedata.

## What changes in s2sdk that touches us

### Headers voltmod and the plugins include that moved or were removed

| Old include | New include | Users |
| --- | --- | --- |
| `eiface.h` (removed) | `engine2/ivengineserver2.h`, `engine2/isource2server.h`, `engine2/isource2engine.h`, `engine2/isource2serverconfig.h`, as each file needs | voltmod: `App/Plugin.cpp`, `Engine/ConVars/ConVars.cpp`, `Engine/Server/Map.cpp`, `Entities/Controller.cpp`, `Host/EngineHooks.cpp`, `Host/EngineInterfaces.cpp`, `Host/Workshop/WorkshopDownloads.cpp`, `Loader/Loader.cpp`; `plugins/anticheat/src/Engine/DetectionFeed.cpp`; `tools/legacy-dummy/legacy_dummy.cpp` |
| `iserver.h` (removed) | `engine2/inetworkgameserver.h`, `engine2/networkgameserverbase.h`, `engine2/serversideclient.h` | `Host/EngineHooks.cpp`, `Host/EngineInterfaces.cpp`, `Host/Workshop/WorkshopDownloads.cpp` |
| `checktransmitinfo.h` (removed) | `engine2/isource2server.h` | `Hooks/Visibility.cpp` |
| `networksystem/netmessage.h` (removed) | `networksystem/inetworkmessages.h` (`CNetMessage`, `NetMessageInfo_t`) | `Engine/ConVars/ConVars.cpp`, `Engine/Net/NetMessage.cpp`, `Hooks/ClientConVars.cpp`, `Hooks/TextMessages.cpp`, `Hooks/Vote.cpp`, `Host/Input/ButtonPresses.cpp`, `Host/Workshop/WorkshopDownloads.cpp`, `Messaging/Messages.cpp` |
| `engine/igameeventsystem.h` | `engine2/igameeventsystem.h` | `App/Plugin.cpp`, `Engine/ConVars/ConVars.cpp`, `Engine/Net/NetMessage.cpp`, `Hooks/ClientConVars.cpp`, `Hooks/TextMessages.cpp`, `Hooks/Vote.cpp`, `Messaging/Messages.cpp` |
| `globalvars.h` | `engine2/gameshareddefs.h` | `Engine/Server/Clock.cpp`, `Engine/Server/Map.cpp` |
| `filesystem.h` | `filesystem/ifilesystem.h` | `Host/EngineInterfaces.cpp`, `Host/Files/ServerAssets.cpp` |
| `inetchannel.h` | `networksystem/inetchannel.h` | `Hooks/ClientConVars.cpp`, `Host/Input/ButtonPresses.cpp` |
| `schemasystem/schematypes.h` (removed) | `schemalib/schematype.h`, `schemalib/schemaclassinfo.h`, `schemasystem/schemasystem.h` | `Entities/Entity.cpp`, `Host/Schema/SchemaFields.hpp` |
| `tier1/convar.h` | `tier0/convar.h` | voltmod: `App/Plugin.cpp`, `App/StatusService.cpp`, `Engine/ConVars/ConVar.cpp`, `Engine/ConVars/ConVars.cpp`, `Engine/Server/ServerCommand.cpp`, `Entities/Controller.cpp`, `Host/Console/VoltCommand.cpp`, `Host/EngineHooks.cpp`; `plugins/anticheat/src/Engine/CheatSimulator.cpp` |
| `Color.h` | `color.h` (case only; breaks Linux, not Windows) | grep `Color.h` |
| `tier1/bufferstring.h` | `tier0/buffer_string.h` | `Host/EngineHooks.cpp` |
| `tier1/utlstring.h` | `tier0/utlstring.h` | `Host/Workshop/WorkshopDownloads.cpp`, `Ui/ScreenEntity.cpp` |
| `tier1/utlvector.h` | `tier0/utlvector.h` | `Entities/Pawn.cpp`, `Hooks/Visibility.cpp`, `Ui/ScreenEntity.cpp` |

Paths are relative to `voltmod/src` unless a plugin or tool is named. The Stronghold submodule and other
closed-source plugins are checked with a grep in phase 3; the table covers what was visible here.

### Sources and include dirs the recipe ships

- `tier1/convar.cpp` and `tier1/keyvalues3.cpp` moved to `tier0_perproject/`. `tier0_perproject/bitbuf.cpp`
  is new there; add it only if the link needs it.
- `tier1/rangecheckedvar.cpp` and `tier1/utlbufferutil.cpp` were removed.
- `entity2/entityidentity.cpp`, `entitykeyvalues.cpp`, `entitysystem.cpp` and `public/tier0/memoverride.cpp`
  are unchanged.
- `public/engine` and `public/tier1` no longer exist. `public/engine2`, `public/networksystem` and
  `public/schemalib` hold most of what moved.
- Protos and `devtools/bin/protoc` are where they were.

### Fixes we get by moving

- `NetworkStateChangedData`: `m_unk101` fixed and named. `Schema/Notify.cpp` builds it on every networked
  write.
- KeyValues3: about 30 commits matching tier0 (sizing, typed arrays, rename, string construction, bool
  conversion), plus `RenameMember`, `OverlayKeysFrom`, `IsArray`, `IsTable`. We compile the SDK's
  `keyvalues3.cpp` and use it for entity spawn keyvalues.
- `CUtlHashtable` relocation onto unconstructed memory and a leak on resize; `CUtlRBTree` construction and
  `CopyFrom`.
- `CUtlString` trivially relocatable; `CBufferString` copy and move; `CUtlLeanVector` relocation.
- `TICK_INTERVAL` truncating to zero.
- `CCommand` trailing fields, `CCommandBuffer` layout, `EmitSound_t`.
- `NetMessageInfo_t` layout and `NetworkMessageId` widened to `int` (CS2), `INetChannel` and
  `INetChannelInfo` signatures, `ILoadingSpawnGroup` vtable, `ISource2Server::unk_401` removed,
  `ISource2ServerConfig::OnClientFullyConnect` taking `CPlayerSlot`.
- `SchemaClassFieldData_t` and `SchemaEnumInfoData_t` updated, which `Host/Schema/SchemaDump.cpp` reads.

### New declarations we use

- `CServerSideClientBase` / `CServerSideClient` with named members, declared virtuals and accessors
  (`GetPlayerSlot`, `GetClientSteamID`, `GetUserID`, `GetNetChannel`, `GetSignonState`, ...).
- `CCheckTransmitInfo::m_nPlayerSlot` in `engine2/isource2server.h`.
- `CRecipientFilter` in `game/shared/recipientfilter.h` (`AddRecipient`, `AddAllPlayers`,
  `MakeReliable`, `RemoveRecipient`, ...).
- Container conveniences: range-for on most utl containers, `CUtlVector` move, iterators and `std::sort`.
  Use them where we touch code anyway; no sweep.

## Phases

### Phase 1: the `s2sdk` Conan package (voltmod)

Replace `conan/recipes/hl2sdk-cs2/` with `conan/recipes/s2sdk/`; delete the old folder outright.

- `conandata.yml`: one version, `2026.10.13`, url `https://github.com/alliedmodders/s2sdk.git`, commit
  `809a2d48...` (full hash at implementation time; take the tip then).
- `conanfile.py`: `name = "s2sdk"`, homepage to s2sdk, `cmake_file_name` `s2sdk`, `cmake_target_name`
  `VoltMod::S2SDK`.
  - `ENGINE_SOURCES`: the three `entity2/*.cpp` and `tier0_perproject/keyvalues3.cpp`.
  - `PLUGIN_SOURCES`: `tier0_perproject/convar.cpp`, `public/tier0/memoverride.cpp`.
  - `HEADER_TREES` unchanged (`public`, `game/shared`, `game/server`, `common`).
  - `includedirs`: drop `public/engine` and `public/tier1`; keep `public/tier0`, `public/entity2`,
    `public/mathlib`; add nothing else unless a build fails on a bare include. Prefer full paths in
    our includes (`engine2/isource2server.h`) over new include dirs.
  - Linux defines: align with s2sdk's `CMakeLists.txt` (`strnicmp`, `_strnicmp`, `strcmpi`, `_alloca`,
    `_finite` are new there). Windows: s2sdk sets `_ITERATOR_DEBUG_LEVEL=0`; add it, since protobuf
    message strings are shared with the game.
  - Library names and folders are unchanged; keep the Linux `lib<stem>.a` copies.
- `cmake/s2sdk-sources.cmake`: rename from `hl2sdk-sources.cmake`; functions become
  `s2sdk_attach_engine_sources`, `s2sdk_attach_generated_sources`, `s2sdk_attach_plugin_support`;
  `HL2SDK_CS2_ROOT` becomes `S2SDK_ROOT`. Delete the old names.
- `test_package/`: point at `s2sdk` and the new target; delete its stale `build/` folder.

Callers to update in the same commit:

- `voltmod/CMakeLists.txt` (`find_package(s2sdk ...)`, `VoltMod::S2SDK`, the three attach calls).
- `voltmod/cmake/VoltModPlugin.cmake` (command check and error text), `voltmod/cmake/VoltModTests.cmake`
  (comment).
- `voltmod/cli/voltmod/toolchain/conan.py`: `PREBUILT_SDK_ARGS` uses `--build=!s2sdk/*`.
- `voltmod/tools/release/sdk_updates.py`: entry renamed to `S2SDK = "s2sdk"`, url
  `https://github.com/alliedmodders/s2sdk.git`, branch `cs2`, same date version format.
- `voltmod/.github/workflows/sdk.yml` and `watch.yml`: any package name or path they mention.
- `.claude/skills/deploy-test/scripts/linux_build.py`: `OWN_RECIPES` entry.
- `voltmod/conanfile.py`: the requirement.

Not in this phase: building the SDK libraries from source with s2sdk's CMake. The prebuilt libs keep
working; revisit only if a `/MT` or ABI problem shows up.

### Phase 2: compile voltmod against s2sdk

Rewrite the includes in the table above. For each former `eiface.h` user, include only the `engine2`
headers it uses. Then fix what the compiler reports, file by file:

- Renamed or retyped engine methods (`ISource2Server`, `ISource2ServerConfig`, `IVEngineServer2`,
  `INetChannel`, `CCommand`). Follow the SDK's new signature; don't wrap it.
- `NetworkMessageId` is now `int`: check `Engine/Net/NetMessage.cpp`, `Host/Input/ButtonPressMessage.cpp`
  and anything storing message ids in a narrower type.
- `Host/Schema/SchemaDump.cpp` and `SchemaFields.hpp` against the `schemalib/*` types.
- `Schema/Notify.cpp` against the fixed `NetworkStateChangedData` constructors.
- `voltmod/include/VoltMod/Engine/EngineTypes.hpp`: forward declarations that now name a different
  class or moved (`IGameEventSystem`, `CGlobalVars`, `INetworkServerService`, ...); keep the list
  accurate, no extras.

Done when `uv run poe build` and `uv run poe test` pass on Windows with the editable voltmod.

### Phase 3: compile the plugins and tools

- `plugins/anticheat`: `DetectionFeed.cpp` (`eiface.h`), `CheatSimulator.cpp` (`tier1/convar.h`).
- `tools/legacy-dummy/legacy_dummy.cpp` (`eiface.h`).
- Grep every plugin, including the Stronghold and other closed-source submodules, for
  `eiface.h|iserver.h|tier1/|engine/|netmessage.h|globalvars.h|filesystem.h|schematypes.h|checktransmitinfo.h`
  and fix what turns up.

### Phase 4: replace gamedata offsets with SDK declarations

Each item deletes the gamedata key, the `Bindings` member, its `bind(...)` line in
`src/Engine/GameData/Bindings.cpp`, its entries in `gamedata/gamedata.jsonc`, and every
"did not bind" check and log message that guarded it. No branch keeps the old path.

| Gamedata key | Replacement | Code that changes |
| --- | --- | --- |
| `CServerSideClientBase::m_nClientSlot` (`ClientSlot`) | `CServerSideClientBase::GetPlayerSlot()` | `Engine/Net/ServerSideClients.*`, `Hooks/ClientConVars.cpp`, `Host/Input/ButtonPresses.cpp`, `Ui/ScreenManager.cpp` |
| `CServerSideClientBase::m_SteamID` (`ClientSteamId`) | `GetClientSteamID()` | its readers (grep `ClientSteamId`) |
| `CServerSideClient::INetworkMessageProcessingPreFilter` (`ClientMessageFilter`) | `static_cast<CServerSideClientBase*>(filter)` | `Engine/Net/ServerSideClients.*`, `Ui/ScreenManager.cpp` |
| `CheckTransmitPlayerSlot` (`VisibilityRecipientSlot`) | `CCheckTransmitInfo::m_nPlayerSlot` | `Hooks/Visibility.cpp` |

With these gone, `Engine/Net/ServerSideClients.cpp` and `.hpp` have nothing left and are deleted; callers
use the SDK accessors directly.

Replace the `EngineClient` tag class in `EngineTypes.hpp` with a forward declaration of
`CServerSideClientBase` (or `CServerSideClient` where the derived class is what the engine passes), and
retype `Bindings::ProcessRespondCvarValue`, `Bindings::SendNetMessage`, `Bindings::ReplyConnection` and
the users in `Hooks/ClientConVars.*` and `Host/Workshop/WorkshopDownloads.*`.

Kept in gamedata on purpose (fact 6 and 7): `GameEntitySystem`, `CNetworkGameServer::m_szAddons`,
`CNetworkGameServer::ReplyConnection`, the `CUserCmd` offsets, and the hooked vtable slots
(`SendNetMessage`, `ProcessRespondCvarValue`, `FilterMessage`), since hooks need a slot index and
taking it from the declaration is a separate decision. Plain calls through those slots may use the
declared virtual instead of the bound slot.

Update `docs/sdk/gamedata.md` (and the doctor check text in `cli/voltmod/checks/doctor.py` if it names a
removed key) to list only the keys that remain.

### Phase 5: replace hand-rolled SDK copies

- `include/VoltMod/Engine/Net/RecipientFilter.hpp`: delete `SingleRecipientFilter` and
  `MultiRecipientFilter`; callers build a `CRecipientFilter`, call `AddRecipient(CPlayerSlot(slot))` and
  `MakeReliable()`. Keep the slot range check where callers take an untrusted slot. Users: voltmod
  `Engine/ConVars/ConVars.cpp`, `Hooks/ClientConVars.cpp`, `Hooks/Vote.cpp`, `Messaging/Messages.cpp`,
  `include/VoltMod/Hooks/Vote.hpp`; Stronghold `Structures/Air/RocketLauncherSystem.cpp`,
  `Vehicles/Vehicle.cpp`, `Weapons/Lock.cpp`. Delete the header; no alias.
- The comment about `PostEventAbstract`'s bitmask overload moves to the one place voltmod posts events.
- Grep voltmod for other structs, enums or flag constants that s2sdk now declares (`TakeDamageFlags_t`
  in `Hooks/DamageLayout.hpp`, `CGameEntitySystem`/`IEntityListener` use in `Entities/EntitySystem.cpp`,
  `CGameResourceService`) and switch to the SDK's where the layout matches. Delete ours.

### Phase 6: docs and repo notes

- `voltmod/docs/consuming-via-conan.md`: the package table row and the `s2sdk_attach_plugin_support`
  section.
- `docs/local-development.md`: the mis-cased include note names hl2sdk headers; check them against
  s2sdk's file names (`Color.h` became `color.h`, and so on).
- `voltmod/CLAUDE.md` (`conan/` line) and the root `CLAUDE.md` if they name the package.
- `voltmod/CHANGELOG.md`: one entry for the SDK switch and the removed gamedata keys.
- Rules in `.claude/rules/` that name hl2sdk paths.

### Phase 7: verify

1. `uv run poe build` and `uv run poe test` (Windows, editable voltmod), then `uv run poe lint`.
2. Linux: `build-linux` in the CI container (or the deploy-test Docker build), since include case and the
   Linux defines change.
3. Local server, with `uv run poe install` and a fresh start. Exercise every path that used a removed
   binding or a fixed layout:
   - custom HUD button presses (`FilterMessage`, client slot from the filter base)
   - client convar queries (`ProcessRespondCvarValue`)
   - visibility and glow (`CCheckTransmitInfo::m_nPlayerSlot`)
   - workshop addon download on join (`SendNetMessage`, `ReplyConnection`, `m_szAddons`)
   - chat, center text, votes and sounds (recipient filters)
   - entity spawn with keyvalues, networked schema writes (KV3, `NetworkStateChangedData`)
   - console commands and convars (`CCommand`, `convar.cpp`)
   - Stronghold rockets, vehicles and lock-on sounds
4. Check the server log for gamedata bind failures; the removed keys must not appear anywhere.

### Phase 8: commit

Branch `feat/s2sdk` in voltmod, cs2-plugins and each touched submodule. Grouped commits:

1. voltmod: s2sdk package and build wiring (phase 1).
2. voltmod: include and API updates (phase 2).
3. voltmod: SDK client and transmit declarations replace gamedata offsets (phase 4).
4. voltmod: `CRecipientFilter` replaces the framework filters (phase 5).
5. voltmod: docs (phase 6).
6. cs2-plugins and submodules: plugin and tool updates (phase 3, phase 5 callers).

No release and no relock in this change; those follow the usual release flow once it's merged.

## Risks

- **s2sdk moves fast.** About 490 commits in a week, many of them file moves. Pin one commit, and expect
  include and rename fixes on each bump. `sdk_updates.py` keeps opening bump PRs; treat them as work,
  not a formality.
- **Layout claims can still be wrong.** s2sdk verifies against binaries, but phase 7's live checks are
  what proves the accessors we switch to.
- **Closed-source submodules** may include SDK headers this plan didn't see; phase 3's grep catches them.
