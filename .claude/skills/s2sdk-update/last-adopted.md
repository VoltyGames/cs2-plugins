# Last s2sdk adoption

The upstream commit whose changes the framework and plugins were last read against and adopted.
The watcher bumps the pin daily without reading anything, so the pin is not this baseline. Update
this file when an adoption is committed.

- s2sdk: `21654ee5` (`origin/cs2`, 2026-11-11), reviewed in full; built against the
  2026.11.11 pin `4220cad5`. The 12 commits between them touch nothing we use.
- voltmod: `861606b0` (2026-11-11), "refactor: use s2sdk's binding, chainer, vector and solid types";
  the workaround is `e594a467`. The previous adoption was `58ffe713` (2026-10-16, s2sdk `e7086d0f`).

## Open workarounds for upstream gaps

- `.claude/notes/2026-11-11-network-message-types.md`: networksystem changed in CS2 build 2000943,
  and s2sdk does not declare the new layout yet.

## Reviewed and not adopted (2026-11-11)

Ask before redoing these; each needs a decision or framework work:

- `cstrike15_usermessages.proto` is shipped but not compiled by the recipe. Compiling it (plus
  `cstrike15_gcmessages`, `gcsdk/*`) would replace the hand-written CustomHudClicked decoder
  (`voltmod/src/Host/Input/ButtonPressMessage.cpp`, id 390) and the reflection field access in
  `Hooks/Vote.cpp`. The cost is a large GC proto set in every plugin.
- `CGameEntitySystem::SpawnEntity`/`SpawnEntities` could replace the `CreateEntityByName`/`DispatchSpawn`
  signatures. But `SpawnProp`, `SpawnLine` and `SpawnBeam` write fields between create and spawn, and
  `g_pNetworkServerService` is never set.
- New SDK features worth exposing: `ISource2GameClients::GetPlayerCommandStatus` (fakelag signal),
  `INetChannelInfo::GetNetworkFlowQuality`, and `ConnectionTypeFlags_t`/`GetClientConnectionType`.
  `Player::IsBot()` counts SourceTV as a bot today.
- Plugin findings that change behaviour:
  - anticheat reads `FL_FAKECLIENT` on the pawn (`src/Engine/Detectors.cpp`), but the SDK says it is set on controllers.
  - admin-system's model effect restores fixed `tm_phoenix`/`ctm_sas` models.
  - admin-system gives T players `weapon_knife_t`, while stronghold gives everyone `weapon_knife`.
  - anticheat's simulator parses `CCommand` by hand.
- Framework APIs plugins hand-roll: weapon vdata (gear slot, weapon type), a voice mute service, and
  player userids.
