# Memory and hot-path fixes (2026-10-01)

Prod `panel-a` (25+ players, all five plugins) went from about 1 GB to 2 GB of RAM. A read-only
review of voltmod and Stronghold found one unbounded growth (a unique entity name per tracer) and
many entity-count and per-tick costs. This plan fixes all of them.

Decided with the user:

- Idle turrets sweep only while a live player is within the turret's range.
- The per-plugin RunCommand and FilterMessage hooks move into the host: one hook each, decoded
  once, raised on every plugin through `IPluginEvents`.

## Execution

- Branch `perf/memory-and-hot-paths` in voltmod, stronghold and cs2-plugins (root only if a
  plugin there changes).
- Commits grouped per topic. No release, no relock.
- Build against the editable voltmod checkout; test on the local server (`uv run poe run`), not
  `/deploy-test`.
- C++ phases run one after another (one build tree).

## Phase 1: voltmod

1. `CallbackRegistry` dispatches by reference: removal during a dispatch is deferred, so no
   per-dispatch copy of each handler.
2. `Visibility::ShowOnlyToTeam`; build the hidden-player array only when someone is hidden; prune
   dead entries even when the transmit offset did not bind.
3. `GlowVision` for a team (`Visibility::CreateTeamGlow`): one clone pair per target, shown to
   the team.
4. Particle control points by entity handle (`CParticleSystem::m_hControlPointEnts`) so a line
   effect needs no target name.
5. `EntitySystem::Find`/`FindAll` without per-call string and vector allocations; game rules
   looked up once per map in `Rounds` and `Vote`.
6. `GameEvents` detaches an engine listener when its last subscription drops.
7. `Damage`'s FireEvent hook removed when no damage with a weapon name is pending.
8. Center-HTML menus send only on change, plus a keep-alive; `CenterHtml` repeats stop when the
   slot changes hands.
9. Host-owned RunCommand hook (`IPluginEvents::OnRunCommand`) and FilterMessage hook
   (`IPluginEvents::OnButtonPress`); `Movement` and `ScreenManager` subscribe through them.
10. `DownloadQueue` forgets a client on a real disconnect.
11. `Database`: per-frame delivery only while jobs are in flight; jobs fail fast while a reconnect
    is backing off; the queue is capped.
12. `HttpClient`: one worker thread with a reused session, a capped wait queue, per-frame delivery
    only while requests are in flight.
13. `MenuStack`: reopening the menu on top replaces it instead of stacking.
14. Malformed button-press warnings rate-limited per slot.

## Phase 2: Stronghold

1. Tracers and laser beams: control point 1 by handle, no `stronghold_line_<N>` names.
2. Sensor tower: one team glow per team instead of one per viewer.
3. Shop preload: one prop per distinct model.
4. Turrets: idle sweep only with a live player in range; fewer sight traces per target pick.
5. `StructureRegistry`: entity-index lookup map; `ClearShot` skips pawns; `RemovePending` only
   when something is pending.
6. Placement: skip the check and ghost move when the aim did not change.
7. Tesla: one entity pass for all grenade classes.
8. Vehicles: parked vehicles skip per-frame work; locked-on set built once per frame; parts move
   only when the pose changed; seat HUD text rebuilt only when it changes; hold-fire and
   hold-crouch writes only on change.
9. HUD: global hides once per screen spawn; `SetBar` only when the step changes; structure panel
   rebuilt only when its card changes.
10. Station system interval; air defense shot lookup; projectile flight allocation.
11. Dropped grenades and launchers: check on the local server whether they pile up; set the
    death-drop convars if they do.

## Phase 3: other plugins

admin-system, main-menu, anticheat and bhop adapt to any API change from phase 1.

## Not in scope

- The shop preload's proper fix (models loaded with the map, `.claude/notes/2026-09-25-structure-model-preload.md`).
- Per-shot muzzle, impact and casing particles stay entities.
- The host's SendNetMessage hook for workshop downloads stays (one hook, cheap filter).

## Progress log

- 2026-10-01: plan written.
- 2026-10-01: phase 1 committed in voltmod (e3c5161..b2bc209), tests and lint pass. Left out:
  - 1.4 particle control points: the Linux schema dump with `CParticleSystem` lives on prod
    (`addons/voltmod/schema/server.json`), and reading prod was denied. Waiting on the user.
  - 1.5 game rules cache: `cs_gamerules` sits near the start of the entity list, so `Find` is cheap.
  - 1.13 menu stack: no plugin re-pushes the same page in a loop.
- Requested on the way: no `for (;;)` loops, terse comments in touched files, snake_case host event
  labels, `Movement::BeforeCommand`/`AfterCommand`, `PluginRegistry::HasCommandListeners`.
- 2026-10-01: phase 2 committed in stronghold (974d88e..364d3ea); admin-system passes `runtime.Slots`
  to `CenterHtml`. Root build against the checkout, 228 plugin tests and lint pass. Local server
  (bots, de_dust2 then de_inferno): both host hooks install, decoded commands reach anticheat's
  dump, game events re-attach after a map change, `volt reload stronghold` reports no leaks.
  Left out, each well under a millisecond a second: `Riders()`'s allocation, `IsLockedOn`'s slot
  loop, the HUD's cached global hides, the structure panel, air defense and projectile flight.
  Dropped grenades and launchers piled up all round (`weapon_auto_cleanup_time 0`); now 30 s, max 40.
- Still open: 2.1 tracer names (needs 1.4), and checks in a client: turret sweep near players,
  sensor tower glow, center-HTML menu flicker at the 100 ms re-send.
