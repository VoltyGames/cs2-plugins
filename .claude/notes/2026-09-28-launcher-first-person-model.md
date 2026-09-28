# Stronghold launcher first-person model (2026-09-28)

Status: fix implemented, not yet seen in a client. The server did not know the launcher subclasses,
so `ChangeSubclass` did nothing and both views kept the Zeus. VoltMod's host now mounts each plugin's
`server-assets/` folder on the server (voltmod checkout, uncommitted, unreleased).

## How first person works (client.dll, 2026-09-25 build)

- There is no server viewmodel. Each drawn weapon gets a client-only `C_CS2HudModelWeapon`
  (`cs2_hudmodel_weapon`), spawned when the weapon is drawn, which copies the weapon's current model.
- A later subclass change rebuilds it only through `OnVDataChanged(SUBCLASS_CHANGED)` (logs "Re-creating
  weapon hudmodel due to vdata subclass model change."), when the client resolves the subclass.
- So a Zeus that has the launcher subclass before its first draw shows the launcher, as
  `LauncherSystem::GiveLauncher` does, provided the server and the client both know the subclass.

## Root cause, checked on the local server

- `subclass_change stronghold_rpg <zeus>` answered "Unknown subclass"; the Zeus kept subclass "31"
  (`m_nSubclassID` `009d6e41`, offset 796) and `weapon_pist_taser.vmdl`.
- pak01 wins over a loose `scripts/weapons.vdata_c` on any `Game` path, server and client alike.
- A folder added with `IFileSystem::AddSearchPath(..., "GAME", PATH_ADD_TO_HEAD, SEARCH_PATH_PRIORITY_VPK)`
  before a map loads makes the subclass known. Added mid-map, it counts only after a map reload.

## The fix (VoltMod)

- `PluginLoader::MountAssets` adds `addons/voltmod/plugins/<name>/server-assets` with the call above when
  the plugin loads, and `UnmountAssets` removes it on unload. `voltmod_add_plugin` installs the folder.
- Stronghold's `server-assets/scripts/weapons.vdata_c` carries the launcher subclasses; deploy no longer
  copies server assets loose into `game/csgo`.

## Still to do

1. `uv run poe meatgg-addon`, then update meatgg (3808651114) in the Workshop Manager: the published
   copy (09-26) has no `scripts/` and no launcher models.
2. Local check: install stronghold, restart the server, then `sv_cheats 1`, `ent_find weapon_taser`,
   `subclass_change stronghold_rpg <index>` must print "Changed entity". Join, buy an RPG, draw the Zeus:
   first and third person should show the RPG.
3. Commit voltmod and the plugins, release voltmod, relock, deploy.
4. The hand-copied `C:/cs2-server/game/csgo/scripts/weapons.vdata_c` is ignored by the server; delete it.
