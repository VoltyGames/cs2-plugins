# Stronghold launcher first-person animation (2026-10-19)

Status: paused before any in-game test. The goal was custom first-person animations for the RPG
and the Stinger (RPG on the shoulder, the rocket leaving the tube, draw and idle). The normal
route is closed; a route that edits Valve's compiled files works offline but was never loaded
in a client. Builds checked: client `client.dll` 2026-10-14, `pak01_dir.vpk` 2026-10-15.

## How first person works now

- Both launchers are Zeus subclasses (`stronghold_rpg`, `stronghold_stinger` in
  `plugins/stronghold/content/scripts/weapons.vdata`) with `m_szAnimClass = "weapon_taser"` and
  `m_szAnimSkeleton = taser.vnmskel`. Background: `2026-09-28-launcher-first-person-model.md`.
- The client's first-person graph is `animation/graphs/viewmodel/viewmodel.vnmgraph`. Its `WPN`
  state machine has a `Pistols` state whose inner machine has one state per pistol (Revolver, USP,
  Glock, CZ75, Elites, P2000, TEC9, FiveSeven, Taser, P250, Deagle). Each is picked by an ID
  comparison on the `weapon_type` parameter and holds a referenced graph.
- The Taser state references `viewmodel_gun.vnmgraph+taser.vnmgraph`: clips `draw_taser`,
  `idle_taser`, `shoot1_taser` (under `animation/anims/viewmodel/pistol/pistol_taser/`),
  `rifle_m249/idle_from_activity_m249`, and the inspect graph
  `viewmodel_inspects.vnmgraph+taser.vnmgraph`.
- The shoot clip never plays: `Pawns::HoldFire` keeps the Zeus from firing so it does not zap.
  First-person fire animations are client-predicted, so the server cannot start one directly.
- Third person uses `animation/graphs/worldmodel/worldmodel.vnmgraph` with
  `worldmodel_gun.vnmgraph+taser`; the server runs it too (hitboxes).
- `weapon_type` almost certainly comes from `m_szAnimClass`: CS2 uses that field to give a C++
  class another weapon's animations (MP5-SD is `_class weapon_mp7` with anim class
  `weapon_mp5sd`; R8 is `_class weapon_deagle` with `weapon_revolver`). Not tested in game.
- Viewmodel graph parameters: `weapon_type`, `weapon_category`, `weapon_extra_info`, `action`,
  `action_reset`, `attack_type`, `attack_variation`, `deploy_variation`, `idle_variation`,
  `inspect_variation`, `inspect_extra_info`, `weapon_ammo`, `weapon_ammo_max`,
  `weapon_ammo_reserve`, `weapon_is_silenced`, `reload_stage`, `weapon_ironsight_amount`,
  `attack_throw_strength`, `weapon_is_legacy_model`, `weapon_action_speedscale`. client.dll binds
  them by name in a constructor around RVA `0x8fca51`; who writes each value was not traced.

## The blocker

The public Workshop Tools cannot compile any AnimGraph2 file. `resourcecompiler.exe` answers
`Failed to find compiler for file` for `.vnmgraph`, `.vnmclip` and `.vnmskel`. `resourcecompiler.dll`
holds the `CNmGraphDoc*` classes and `AssetBrowse( vnmclip )` strings, but no registered compiler.
The CS2 tools ship no AnimGraph2 editor either.

## The route that works offline

Edit Valve's compiled files with the ValveResourceFormat (VRF) library instead of compiling new
ones.

- VRF **master** can read a compiled resource, change its KV3 data and write it back
  (`Resource.Serialize`). The NuGet release 20.1.7467 cannot: it uses ValveKeyValue 0.70, whose
  `KVDocument` and `KVObject` indexers are read-only. Master uses ValveKeyValue 0.72.
- Verified 2026-10-19: `viewmodel_gun.vnmgraph+taser.vnmgraph_c` read, re-serialized and re-read
  (11,314 bytes became 14,849: VRF writes uncompressed binary KV3 v5), and a version with two data
  slots swapped also re-read. Never loaded in a client.
- Setup: `git clone --depth 1 https://github.com/ValveResourceFormat/ValveResourceFormat.git vrf`,
  then a .NET 10 console project with `dotnet add reference vrf/ValveResourceFormat/ValveResourceFormat.csproj`.
  The core of the spike:

  ```csharp
  using var resource = new Resource { FileName = Path.GetFileName(input) };
  resource.Read(input);
  KVObject data = ((BinaryKV3)resource.DataBlock!).Data;   // implicit KVDocument -> KVObject
  var slots = KVObject.Array();                             // arrays are rebuilt, not edited in place
  foreach (var slot in data["m_resources"]) slots.Add(slot);
  data["m_resources"] = slots;
  using (var stream = File.Create(output)) resource.Serialize(stream);
  ```

- Changing a resource reference also needs the RERL block (external references, keyed by a
  64-bit hash of the name) to list the new file; not tried yet.

### Compiled graph layout

`Source2Viewer-CLI -i <file>_c -b DATA` prints it. Top-level keys: `m_variationID`, `m_skeleton`
(`animation/skeletons/characters/viewmodel.vnmskel`), `m_persistentNodeIndices`, `m_nRootNodeIdx`,
`m_controlParameterIDs`, `m_virtualParameterIDs`, `m_virtualParameterNodeIndices`,
`m_referencedGraphSlots`, `m_externalGraphSlots`, `m_nodePaths`, `m_nodes`, `m_resources`.

- `m_nodes` is a flat list of `CNm<Type>Node::CDefinition` objects linked by index: 285 nodes in
  the taser variation (state machines, states, transitions, ID/float comparisons, clip nodes,
  selectors, one referenced-graph node).
- No instance memory layout is stored, so appending nodes looks possible.
- Taser variation `m_resources`: `[0]` shoot1_taser, `[1]` inspects graph, `[2]` idle_taser,
  `[3]` draw_taser, `[4]` idle_from_activity_m249.

### Compiled clip layout

VRF's `ValveResourceFormat/Resource/ResourceTypes/ModelAnimation2/AnimationClip.cs` decodes it;
an encoder is its inverse.

- Keys: `m_skeleton`, `m_nNumFrames`, `m_flDuration`, `m_bIsAdditive`, `m_trackCompressionSettings`,
  `m_compressedPoseData` (bytes), `m_compressedPoseOffsets` (per frame, in 16-bit units),
  `m_secondaryAnimations` (nested clips; for the viewmodel, the weapon skeleton's tracks), `m_events`,
  `m_syncTrack`, `m_rootMotion`, float curves.
- Per track settings: translation ranges X/Y/Z, scale range, constant rotation, and static flags
  for rotation, translation and scale.
- Per frame, per track, in order: rotation as 3 ushorts (smallest-three quaternion, 15-bit
  components in `[-1/sqrt2, 1/sqrt2]`, largest index in the top bits of the first two words),
  translation as 3 ushorts normalized into its range, scale as 1 ushort. Static parts are skipped.
- The clip source format (for reference): `m_sourceFilename` (a DMX),
  `m_animationSkeletonName = viewmodel.vnmskel`, `m_secondaryAnimationSkeletonNames = [taser.vnmskel]`,
  event tracks (shoot1_taser fires `weapon_taser_glow.vpcf` on `muzzle_flash`). Decompiled clips
  come with a DMX that Blender Source Tools can import as a starting pose.

## Planned design

Lowest risk: replace only `viewmodel_gun.vnmgraph+taser.vnmgraph_c`, shipped in meatgg, and
branch inside it. A real Zeus keeps Valve's clips; the launchers play new ones.

- Keep `m_szAnimClass = "weapon_taser"`, so the root viewmodel graph, third person and the
  server stay untouched.
- Branch key: a value the subclass sets and the graph sees, such as `weapon_ammo_max` from
  `m_iMaxClip1` (Zeus 1, RPG 2, Stinger 3). That this parameter reads the subclass's vdata is not
  verified.
- Launch trigger: the server drops the launcher's clip to 0 when it fires and the graph moves on
  `weapon_ammo`, so no client-side shot is needed. Also not verified.
- New clips (draw, idle, launch, perhaps inspect) animated in Blender on `viewmodel.vnmskel` plus
  `taser.vnmskel`, written as `.vnmclip_c` by the encoder.

The alternative, a new anim class per launcher, needs patched copies of `viewmodel.vnmgraph`
(client) and `worldmodel.vnmgraph` (client and server, through `server-assets`).

## Risks

- A malformed graph or clip can crash every client that has meatgg, on any server.
- Valve changes these files with weapon updates; each one means patching again, like
  `weapons.vdata`.
- Testing needs the replacement to outrank `pak01` on the client. Loose files in `game/csgo` lose
  to `pak01`; a Workshop upload waits for moderation. A temporary `Game` line in the client's
  `gameinfo.gi` pointing at a dev folder is one option (no BOM, keep CRLF).

## Next steps when resumed

1. Re-serialize the taser variation with `[0]` and `[2]` swapped (idle plays the shoot clip),
   mount it, and confirm a client loads it without crashing.
2. Add the branch on `weapon_ammo_max`; confirm a real Zeus and the RPG animate differently.
3. Write one clip with the encoder (start from a re-encoded `idle_taser`) and confirm it plays.
4. Only then animate in Blender.

## Cheaper options considered

- Borrow another gun's first- and third-person animations: set `m_szAnimClass` and
  `m_szAnimSkeleton` on the subclasses and rebuild the launcher models on that gun's bones.
  Candidate skeletons and their bones: AWP (`clip`, `econ`, `muzzle`, `rail`, `bolt_action`,
  `trigger`), Nova and MAG-7 (`pump`), M249 and Negev (`ammobox` and bullet chains).
- Show the warhead leaving in first person: a `stronghold_rpg_fired` subclass whose model has no
  warhead, switched in on fire. The client rebuilds the first-person model on a subclass change.

## Zeus bones (no change needed)

- The stock `weapons/models/taser/weapon_pist_taser.vmdl_c` still has `weapon`, `weapon_offset`,
  `taser_meter`, `ag1_hand_r`, `trigger`, the same as every launcher DMX and `.vmdl`.
- `animation/skeletons/weapons/taser.vnmskel` names them differently: `econ` sits where
  `ag1_hand_r` is, and `taser_chargemeter`, a child of `econ`, sits where `taser_meter` is. Valve's
  own model works with that, so the launchers stay on the model's names.

## Weapon icon (on hold)

The bottom-right weapon list takes the icon from the item definition, not the subclass. client.dll
(around RVA `0xebaa79`) reads the def index (Zeus 31), looks up its name `weapon_taser`, drops
`weapon_` and loads `file://{images}/icons/equipment/taser.svg`. The only option is replacing
`panorama/images/icons/equipment/taser.vsvg` in meatgg: both launchers share it and every real Zeus
on a meatgg server shows it. `items_game.txt` has no spare weapon definitions left (only
`weapon_knifegg` and `weapon_healthshot` besides the Zeus).

## Done alongside

- `weapons.vdata` re-synced with the game on 2026-10-19: only the AUG's
  `m_flDisallowAttackAfterReloadStartDuration` changed (3.766667 to 3.2, three places). Compiled,
  installed locally, `server-assets` refreshed; players get it with the next meatgg upload.

## Tools

- Source2Viewer-CLI: `gh release download --repo ValveResourceFormat/ValveResourceFormat --pattern cli-windows-x64.zip`.
  `-i pak01_dir.vpk -l -f <path>` lists, `-o <dir> -d -f <file>_c` decompiles, `-i <file>_c -b DATA`
  prints compiled data. Copy single files to scratch before decompiling models.
- The scratch spike (`%TEMP%\claude\s2v\`) is temporary; rebuild it from the snippet above.
