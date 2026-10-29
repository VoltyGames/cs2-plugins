---
name: sync-game-files
description: After a CS2 update, check whether the game changed gameinfo.gi, scripts/weapons.vdata or the game models Stronghold content is built from, and resync our copies when it did. Use for "did the update change gameinfo", "sync weapons vdata", "resync game files", "check the cs2 update".
---

# Sync game files after a CS2 update

The repo keeps copies of game files, and some Stronghold content is built from game models:

| Game file | Ours |
| --- | --- |
| `game/csgo/gameinfo.gi` | `workshop/gameinfo.gi` (LF, plus the skillgroups include the Workshop Manager needs) and `deploy/files/panel/gameinfo.gi` (stock plus one comment line) |
| `scripts/weapons.vdata_c` | `plugins/stronghold/content/scripts/weapons.vdata`: stock plus the `stronghold_*` entries before the final `}` |
| `agents/models/ctm_sas/ctm_sas.vmdl_c` | the `Skeleton` in `models/stronghold/prone/prone.vmdl` and the armature in `prone.blend` |
| `weapons/models/taser/weapon_pist_taser.vmdl_c`, `weapon_pist_taser_mag.vmdl_c`, `animation/skeletons/weapons/taser.vnmskel_c` | the bones, attachments, `weapon_metadata` and skeleton reference in `models/stronghold/rpg/` and `stinger/` |

[baseline.json](scripts/baseline.json) holds the hash of each game file as of the last sync, with the
build it came from.

## 1. Check

```bash
.venv/Scripts/python -I .claude/skills/sync-game-files/scripts/check.py
```

The script reads the client's `pak01_dir.vpk` and gameinfo.gi, prints `current` or a diff for each
copy, and exits 1 when something needs action. Pass `--client <folder>` for a client outside the
default Steam library.

## 2. Act on the result

**The skillgroups include is missing.** Every CS2 update drops it. Run the check again with
`--add-include`. That backs the file up to `%TEMP%/gameinfo.gi.bak` and inserts the line with
byte replacement, keeping CRLF and adding no BOM. Do not use `sed`, which mangles the tabs. A bad
gameinfo.gi stops `resourcecompiler` and CS2.

**gameinfo.gi changed.** Add the include first. Then copy the client file to
`workshop/gameinfo.gi` with LF line endings, and to `deploy/files/panel/gameinfo.gi` without the
include and with its comment line kept. Review both diffs.

**A game source changed.** Decompile it with the Source2Viewer CLI. It is a downloaded binary, so
keep it in its own scratch folder and expect the user to approve each run:

```bash
D="$TEMP/s2v"; mkdir -p "$D"
[ -f "$D/Source2Viewer-CLI.exe" ] || (cd "$D" && gh release download \
  --repo ValveResourceFormat/ValveResourceFormat --pattern cli-windows-x64.zip && unzip -oq cli-windows-x64.zip)
CLIENT="C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive"
"$D/Source2Viewer-CLI.exe" -i "$CLIENT/game/csgo/pak01_dir.vpk" -o "$TEMP/stock" -d -f <path>
```

For a model, copy the single `_c` file to scratch first and dump it with
`Source2Viewer-CLI -i <file>_c -b DATA`.

- `weapons.vdata_c`: run the check with `--stock-weapons "$TEMP/stock/scripts/weapons.vdata"`.
  If the diff touches `weapon_taser`, carry the new or changed keys into each `stronghold_*`
  entry by hand: both are copies of it with their own model, damage and award. Then rerun with
  `--write-weapons`, which rewrites ours as stock plus the current entries.
- `ctm_sas.vmdl_c`: compare the skeleton's bone names, parents and rest transforms with the
  `Skeleton` in `prone.vmdl`. If they moved, update the armature in `prone.blend` and regenerate
  the poses with `prone_pose.py` and `prone_export.py` (use the `3d-model` skill).
- The taser files: compare bone names, attachments and `weapon_metadata` with `rpg.vmdl` and
  `stinger.vmdl`, and check that the referenced paths still exist.

A hash can change when Valve only recompiles a file. If nothing that we copy changed, the content
needs no edit.

## 3. Compile and record

After editing content:

```bash
uv pip install --reinstall-package voltmod ./voltmod
.venv/Scripts/voltmod.exe content compile stronghold <folder> --install client
.venv/Scripts/voltmod.exe content server-assets stronghold
uv sync
```

Once every copy matches, run the check with `--record` to save the new hashes and build. It must
then exit 0.

Commit Stronghold content in the Stronghold repo and the rest here, with the `commit` skill:
`chore: resync <file> with cs2 build <build>`. Clients get the content through the meatgg addon,
so changed content also needs the `meatgg-addon` skill and an upload.

## 4. Report

For each row of the table, tell the user whether it is current, was restored or was resynced, and
summarise what the game changed.
