---
name: meatgg-addon
description: Recompile all Stronghold workshop content into the CS2 client, refresh Stronghold's server-assets, check the client gameinfo.gi has the skillgroups include, and fill the meatgg addon for the user to upload in the Workshop Manager. Use for "build the meatgg addon", "compile workshop files", "update the workshop addon", "prepare meatgg for upload".
---

# Prepare the meatgg addon

The user uploads the meatgg addon with the Workshop Manager. This skill gets it ready.
You never publish it yourself.

| Step | Result |
| --- | --- |
| 1. Fix the client gameinfo.gi | The skillgroups rank icons get packed |
| 2. Compile Stronghold content | `csgo_addons/stronghold` and the client's loose `game/csgo` are current |
| 3. Refresh server-assets | `plugins/stronghold/server-assets/` matches the compile |
| 4. Fill meatgg | `game/csgo_addons/meatgg` holds every screen, Stronghold content and rank icons |
| 5. Report | The user knows what changed |
| 6. After the upload | The client gameinfo.gi is stock again; changes are committed |

Close the CS2 client and server first: installing into a running game fails.

## 1. Fix the client gameinfo.gi

The Workshop Manager packs only the folders in `VpkDirectories` of
`<client>/game/csgo/gameinfo.gi`. A CS2 update rewrites the file and drops this line, which must
follow the `panorama/images/custom_game` include:

```text
			"include"       "panorama/images/icons/skillgroups"
```

- Back the file up to the scratchpad and edit it with Python byte replacement. Keep CRLF and do not
  add a BOM: a bad gameinfo.gi stops `resourcecompiler` and CS2. Do not use `sed`, which mangles
  the tabs.
- Then copy it to `workshop/gameinfo.gi` with LF line endings. That file is the reference copy.

## 2. Compile Stronghold content

Each `voltmod content compile` call handles one folder and does not recurse, so loop over every
folder that holds a source:

```bash
cd plugins/stronghold/content
folders=$(find . -type f \( -name '*.vmdl' -o -name '*.vpcf' -o -name '*.vsndevts' -o -name '*.vdata' \
  -o -name '*.wav' -o -name '*.mp3' \) -exec dirname {} \; | sort -u | sed 's|^\./||')
cd ../../..
for d in $folders; do
  uv run voltmod content compile stronghold "$d" --install client > "$TEMP/compile_${d//\//_}.log" 2>&1 \
    && echo "ok $d" || echo "FAIL $d"
done
```

- Run it in the background, because it takes several minutes. Read the log for any `FAIL`.
  `got } in key in file gameinfo` means gameinfo.gi is broken.
- Leave out `--install server`. The server loads Stronghold content from server-assets.

## 3. Refresh server-assets

```bash
uv run voltmod content server-assets stronghold
git -C plugins/stronghold status --short
```

An empty status is normal when no source has changed, because the compile is deterministic.

## 4. Fill meatgg

```bash
uv run poe meatgg-addon
```

Check that `game/csgo_addons/meatgg/panorama/images/` has `icons/skillgroups/` and the
`custom_game/` sets, such as `stronghold_kills/`.

## 5. Report

Tell the user:

- whether gameinfo.gi needed the line
- how many folders compiled
- whether server-assets changed
- that meatgg is ready to update in the Workshop Manager

After the upload, Steam moderation has to approve it before players get it. See the
`workshop-addon-client-cache` memory.

## 6. After the user uploads

Restore the client gameinfo.gi from the step 1 backup, then commit with the `commit` skill.
