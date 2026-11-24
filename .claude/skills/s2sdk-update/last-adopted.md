# Last s2sdk adoption

The upstream commit whose changes the framework and plugins were last read against and adopted.
The watcher bumps the pin daily without reading anything, so the pin is not this baseline. Update
this file when an adoption is committed.

- s2sdk: `58bebeb6` (`origin/cs2`, 2026-11-13), reviewed in full; pinned as 2026.11.13.
- voltmod: `b73bfb98` (2026-11-23), "refactor: use s2sdk's NetMessageInfo_t and drop the message type
  workaround"; it replaced `MessageTypes.*` with the SDK's `NetMessageInfo_t` and `INetworkMessages`.
  The previous adoption was `861606b0` (2026-11-11, s2sdk `21654ee5`).

## Open workarounds for upstream gaps

- `CSource2Server::GameFrame` in `gamedata.jsonc` (voltmod `8f69a10b`): CS2 build 2000950 added an
  `ISource2Server` virtual between `GameCreateNetworkStringTables` and `WriteSignonMessages`, so every
  SDK slot from there on is one short and the SDK's `GameFrame` is `ApplyGameSettings`. Once s2sdk
  declares it, hook `&IServerGameDLL::GameFrame` again in `Host/EngineHooks.cpp` and drop the entry and
  `Bindings::GameFrame`. Until then call no `ISource2Server` virtual past `GameCreateNetworkStringTables`
  through the SDK.
- `CBaseEntity::SubclassVData` in `gamedata.jsonc`: the SDK declares no VData accessor, so
  `Entity::FindWeaponData` reads the pointer 4 bytes past the schema's `m_nSubclassID`. Re-check it
  after a CS2 update by comparing `BaseName` with `ClassName()` for stock weapons.

## Reviewed and declined (2026-11-11)

Settled; don't re-propose these unless what each depends on changes:

- `CGameEntitySystem::SpawnEntity`/`SpawnEntities`: they create and spawn in one step through a loading
  spawn group, so nothing can be written in between. `SpawnProp`, `SpawnLine` and `SpawnBeam` set the
  owner, a particle control point, and beam widths, end and colour between `Create` and `Spawn`; these are
  schema fields, not key values. `g_pNetworkServerService` is easy to set, since the host already resolves
  `NetworkServerService`. But the `CreateEntityByName`/`DispatchSpawn` patterns have never broken in a CS2
  update, and swapping them would add `IGameSpawnGroupMgr`/`ILoadingSpawnGroup` virtuals.
- `IServerGameClients::GetClientConnectionType`: `Player::IsSourceTV()` reads the controller instead.
- `INetChannelInfo::GetNetworkFlowQuality`: add it next to `NetChannels::GetCommandStatus` when anticheat
  needs to discount a lossy connection. It only corrects for latency today (`Engine/ViewLag.cpp`), and no
  false positive has been traced to packet loss.
- anticheat's `Detect/WeaponClass.cpp` table stays name-based. `weapon_fire` gives only a name, the table
  lives in the SDK-free tested core, and VData would change the ceilings: `CSWeaponType` puts G3SG1 and
  SCAR-20 with the snipers, but the table gives them the rifle ceiling, and no field separates deagle and
  revolver from the other pistols.
- Stronghold's `Dev/GearSlots.cpp` keeps names for the item it is about to give. `MakeRoom` removes the
  old weapon a tick before the give, so the new weapon has no entity to read yet, and looking VData up by
  name would need a new signature. Carried weapons use `FindWeaponData`.

## Open, not s2sdk

- anticheat's `Engine/CheatSimulator.cpp` registers raw `ServerCommand`s and parses `CCommand` and
  slot-or-steamid64 by hand (`ResolveSlot`). The framework's typed server-only commands with a target
  argument would replace that. It's a debug tool, so this is optional cleanup.
