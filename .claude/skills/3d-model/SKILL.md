---
name: 3d-model
description: Make, reskin or animate a prop for a plugin's workshop addon in Blender, or give one FX (glow, moving parts, particles), then compile, install and wire it in. Use for any new or changed .vmdl or .vpcf, such as "make a model for X", "reskin X", "animate X" or "add particles to X".
---

# 3D models and FX

Build, reskin or animate a prop for a plugin's workshop addon, or give it FX: a glow, moving parts
or a particle effect. Models are built in the user's open Blender session through the `blender`
MCP and Blender Source Tools. Particle effects need no Blender.

The flow: check the tools, read what the plugin expects, build, review with the user, then export,
compile, wire into the plugin, clean up and report the triangle counts. Nothing is exported before the
user approves.

## Tools

| Tool | What it does |
| --- | --- |
| `uv run modelkit check` | Checks Blender, Source Tools, Codex, Git LFS and the Workshop Tools |
| `uv run modelkit audit` | `textures`, `uv`, `compiled` and `triangles`: why a model looks flat or blurry, and what it can lose |
| `uv run modelkit render` | Renders a whole model at eye level, for concept work |
| `uv run modelkit optimize` | Trims triangles, keeping a part's trim only if renders from all round still match |
| `uv run modelkit particles` | Checks `.vpcf` field names; lists a class's fields and the game's particle textures |
| `uv run voltmod content compile` | Compiles one model or particle folder and installs it |
| `tools/modelkit/src/modelkit/blender/` | The helpers you run inside Blender, below |
| `examples/jump_pad.py` | A skinned, animated prop. Read it before building one |
| `examples/teleporter.py` | Glow, team colour and FX animations. Read it before adding FX |

| Module | For |
| --- | --- |
| `blender.session` | Status, scenes, opening models, cleanup |
| `blender.surfaces` | Textures and preview materials |
| `blender.shapes` | Mesh parts |
| `blender.objects` | Finishing, joining and editing parts |
| `blender.rig` | Skeleton and actions |
| `blender.preview` | Renders and the user's viewport |
| `blender.export` | DMX export and the `.blend` |
| `source2.modeldoc` | `.vmat`, `.vmdl` and `.vpcf` writers and readers; also runs without Blender |

`modelkit.blender` and `modelkit.source2` run on Blender's Python 3.13: no newer syntax and no
packages beyond numpy there. The CLI runs on the repository's Python.

One Blender unit is one Source unit; +X is forward and +Z is up. A player is 32 × 32 × 72 units,
with eyes at 64.

## 1. Check the tools

```bash
uv run modelkit check <plugin>
```

Then load the kit in Blender:

```python
import sys

sys.path.insert(0, r"<repo>/tools/modelkit/src")
import modelkit.blender

modelkit.blender.reload()
from modelkit.blender import session, surfaces, shapes, objects, rig, preview, export
from modelkit.source2 import modeldoc

result = session.status()
```

Stop and tell the user if:

- Blender or its MCP doesn't answer.
- `source_tools_enabled` is false.
- `modelkit check` reports MISSING. Codex only matters for new textures, and a running CS2 only blocks
  installing.

If the user has unsaved changes, work only in the model's own scene.

## 2. Pick the path

| Situation | Start with |
| --- | --- |
| A new model | Step 3, then `session.scene(name, "models/<plugin>/<model>/")` |
| A model with a `.blend` | `session.open_model(<blend>)`, which opens every part's scene |
| A model with DMX files only, such as a stand-in | `session.import_dmx(scene, folder, meshes, animations)`; check it, then `export.remember(...)` |
| New textures only | Step 4, then step 8 |
| FX | A glow or a moving part: open or import the model, then steps 5 and 6. A particle effect: [Particles](#particles) |

A model folder keeps one `.blend`, named after the folder, with one scene per part, since each
part is its own `.vmdl`. `open_model` refuses names the session already holds, because Blender
would rename a material to `x.vmat.001` and break the DMX. Pass `replace=True` only to reload over
your own copy.

## 3. Read what the plugin expects

Before designing, find what the plugin assumes about the model. Keep every name it uses, or change
the code in the same task.

- **Path:** grep the plugin for `.vmdl`. In Stronghold it's `src/Assets/Catalog.cpp`.
- **Size:** the `.vmdl` scale, placement box, trigger radii (the jump pad's `Launcher`) and offsets
  measured on the mesh, such as muzzles and each part's `At`.
- **Names:** attachments, animations, material groups (`Skin`) and bones.
- **Assets doc:** the plugin's `docs/assets.md` has the addon layout and licence status.

## 4. Textures

Prefer a baked set over tiled textures: `uv run modelkit bake <plugin> <model>` unwraps the
named materials into one atlas, bakes CC0 materials from Poly Haven or ambientCG with worn edges,
grime, dust and streaks into colour, roughness, metalness and normal maps (no AO map: the game
shadows the model itself), and stamps the
maker's mark. Its recipe is `plugins/<plugin>/bake/<model>.json`; the format is in
`modelkit/baking.py`, and `plugins/stronghold/bake/wall.json` is a worked one.

- It previews first: renders in `build/bake/<plugin>/<model>/`, the model folder untouched. Show
  the user, tune the recipe, bake again.
- `--write` ships the preview: textures and `.vmat` into the model folder, the `.blend` saved,
  the DMX re-exported, the replaced `.vmat` files and their unused textures deleted. Then compile.
- Structures get solid olive drab with light wear (the `olive_drab` finish in any Stronghold
  recipe): keep grime, dust and streaks near 0.1 and `normal_strength` near 0.5, since heavier
  weathering reads as noise in game. Recipe colours are linear, as Blender takes them.
- Leave `size` out: each part bakes at the smallest of 512, 1024 and 2048 reaching 12 pixels per
  game unit. Props seen up close set `"density": 16`.
- To re-bake a model whose `.blend` already holds its baked material, pass
  `--source <revision>`: a commit of the plugin's repo from before its first bake.
- Models with hand-made single-atlas textures (tank, watchtower, helicopters and the rest
  without a baked recipe) keep them: re-baking them read flatter and blurrier in game. Their
  recipe holds only `marks`, and `uv run modelkit mark <plugin> <model>` stamps those onto the
  existing colour texture once.
- Keep recipes out of `content/`: `voltmod content compile --prune` deletes files nothing
  references there.
- A finish with `"artwork": true` keeps the surface's own colour texture (hazard stripes, signs)
  and takes only roughness, normal and wear from the library material.

For a texture no CC0 material covers, generate one. List `~/.codex/generated_images/` before the
first run, so cleanup knows which folders are new. Then run Codex in the background while you
work:

```bash
codex exec --skip-git-repo-check --sandbox workspace-write -C "<scratchpad>/tex" "Use the imagegen skill (built-in image_gen tool) to generate <name>.png: albedo texture for a low-poly CS2 prop; perfectly seamless and tileable on both axes; flat orthographic; evenly lit albedo only (no baked shadows, highlights, perspective or vignette); square 1024x1024; no text, logos or watermark. Subject: <material>. Copy the final image into the current directory as <name>.png."
```

- Look at every result. Brushed metal turns into wood grain on curves, so ask for powder-coated or
  speckled metal.
- `surfaces.replace_texture(generated, color_png, normal_png, strength)` installs a texture at
  1024 px under the existing name, so every `.vmat` stays valid, and rebuilds its normal map. Use a
  strength of about 1.5 for painted metal and 10 for raised patterns.
- `surfaces.brightened` makes a lighter or darker variant. `surfaces.solid` makes glow colours and
  masks.

## 5. Build or edit

Write the build as a scratchpad script and run it with `execute_blender_code`. Stay in the model's
scene, and give imported references a scene of their own.

- **New parts:** make the geometry with `shapes` and cut holes with `objects.cut`.
  `objects.finish` bevels, maps UVs, sets the material and binds the part to a bone.
  `objects.join` makes the render mesh and `objects.hull` the collision.
- **A finished mesh:** `objects.vertices(body, material=..., bone=...)` picks a part, and
  `objects.transform` moves or scales it. Add parts with `objects.join([body, *parts], body.name)`
  and repoint a renamed material with `objects.replace_material`. To only resize, use
  `write_vmdl(scale=…)`.
- **Size:** compare against a player. A floor prop over about 40 units wide looks oversized.
- **Detail:** add bevels, a trim material, bolts, vents, an inset and normal maps. 5–12k
  triangles is fine.
- **Glow:** keep it to thin lines and small markers at glow 1.0. A large glow reads as flat colour,
  even under a grate; light it from a core that fades to dark instead, like the teleporter's well.
- **Team colour** goes on a thin glowing part that players see from a distance, such as a strip,
  with its own material remapped in `blue`/`red` material groups.

### Triangles

Trim a new or existing model only where nobody can see the difference: it must render the same
before and after.

| Trim | Keep |
| --- | --- |
| Faces buried inside another closed part, such as a wing root in the fuselage | Round parts' sides: 12 or more on a thin rod, 16–32 on a drum or pod |
| Caps hidden where a tube or band meets a surface | Bevels, rounded ends and panel edges you can see |
| Bevels on tiny parts, such as switches and straps | Rings along a curve that keep its outline smooth |

- `objects.join` smooth-shades below 35°, so a round part with fewer than 11 sides shades as flat
  facets and reads as a box.
- Render the same views before and after a trim. Put back anything that reads flatter or boxier.
- `uv run modelkit audit triangles <plugin> -m <model>` counts degenerate, coplanar and hidden
  triangles per part. `uv run modelkit optimize <plugin> <model>` trims them in the `.blend` and
  keeps a part's trim only when ten renders from all round still match; it takes minutes. The
  hidden-face test misses faces seen through small holes, such as under a grate, so expect the
  render check to reject those parts. Re-export the DMX and compile after it.

## 6. Animate

`rig.skeleton` makes the bones and skins the mesh by vertex group. `rig.animate` records an action
from per-bone `(frame, move, turn)` keys at 30 fps, relative to rest. `rig.eased` fills in the
frames between keys without overshoot. `export.remember` saves the export settings in the
`.blend`.

- **Exaggerate:** a 10-unit lift looked static in game. Crouch, overshoot, then bounce to rest.
- **Idle:** anything that should look alive needs a moving `idle` loop, and the plugin must start
  it (step 9). A loop ends on its first key.
- **Turning parts** end every action on whole turns, so the loop picks up cleanly after a
  one-shot.
- **FX as animation:** put a glowing part on its own bone and move it. The teleporter's light
  strip lifts off as a hoop and sweeps past the player, which made a planned particle burst
  unnecessary.
- **Check** a few frames of each action with `preview.contact_sheet`, looking for parts that clip.

## 7. Review with the user

- Stage the scene with `preview.stage()` and show the model with `preview.frame_viewport`.
- Render stills from a player's view with `preview.render`: about 64 units up, 60–80 away.
- Tell the user how to play an action: select the armature, pick the action in the Action Editor,
  press Space.
- Iterate. Export nothing before they approve.

## 8. Export and compile

```python
export.write_dmx(scene, model_dir)  # meshes, hull, one DMX per action
# every part's scene; Git LFS, not the compile
export.save_blend(scenes, model_dir + "/<folder>.blend")
modeldoc.write_vmat(...)  # only for new or changed materials
modeldoc.write_vmdl(...)  # only when meshes, animations, groups or attachments change
```

Stop the CS2 server and client first; installing into a running game fails.

```bash
uv run voltmod content compile <plugin> models/<plugin>/<model> --install client --install server
```

- `export.write_dmx` refuses `.001` materials and leaves object references stale, so look objects up by
  name afterwards.
- `voltmod content compile` mirrors the folder from the plugin's `content/` into the Workshop
  Tools content folder, recompiles it from scratch and copies the result to each install target.
  `--addon` picks another `csgo_addons` folder than the plugin's name.

## 9. Wire it into the plugin

- Point the plugin at the `.vmdl`, and update the placement box, trigger radii and measured
  offsets. Resize with `write_vmdl(scale=…)`, which scales the mesh, hulls and animation; write
  the offsets in code at that final size.
- Start a loop with the `SetAnimationLooping` input; in Stronghold, name it in `Idle` in
  `StructureAssets`. `prop_dynamic` has no `SetAnimation` input (`game/core/base.fgd`).
- Play a one-shot with `Entity::PlayAnimation(animation, idle)`, which returns to the loop after.
- Record new or replaced assets, and how they were made, in the plugin's assets doc.
- Build with `build-local`, install with `uv run poe install <plugin>`, and check that the
  installed DLL's hash matches the build.

## 10. Clean up

The task is done when nothing it created is left without a purpose. Deploying is not the end: the
user tests in game and often asks for changes, so keep the build script, renders and generated
images until they say the model is finished or ask to commit.

- **Blender:** `session.remove_scene` for every scene the task made other than the model, then
  `session.purge()`. Leave the user's own scenes alone.
- **Model folder:** `voltmod content compile ... --prune` deletes sources nothing names, such as replaced textures.
  Delete stray exports by hand: `anims/`, or a DMX named after a Blender object.
- **Game folders:** if a model or effect folder was renamed or removed, delete its old copy under
  `content/csgo_addons/<addon>/`, `game/csgo_addons/<addon>/` and `game/csgo/`, on the client and
  the server.
- **Plugin:** remove constants, config and doc lines that only served the replaced model.
- **Scratch:** once the user is done, delete the scratchpad files and the
  `~/.codex/generated_images/` folders your runs added.
- **Git:** `git status` shows only the files you meant to change. Commit with the `commit` skill
  when asked.

## 11. Report

End with each exported model's triangle count, and the count before for a model you changed:
`sum(len(p.vertices) - 2 for p in ob.data.polygons)` on its render mesh.

## Particles

Use a particle effect for sparks, smoke or light that fades. Try glow and animation first: they
live in the model, while an effect is a separate file the plugin must spawn, precache and remove.

1. **Write** each effect into `plugins/<plugin>/content/particles/<plugin>/<effect>/` with `modeldoc.write_vpcf`,
   built from `modeldoc.op(...)` operators. A team variant is its own file; a part several effects
   share is a child.
2. **Check the field names.** `resourcecompiler` silently drops fields it doesn't know, so a typo
   compiles into an effect without that setting. `uv run modelkit particles fields <class>` prints the real
   names: `C_INIT_RandomLifeTime` takes `m_fLifetimeMin`, not `m_flLifetimeMin`.
3. **Check, then compile and install.** Fix every field `modelkit particles check` reports before
   compiling:

   ```bash
   uv run modelkit particles check plugins/<plugin>/content/particles/<plugin>/<effect>/*.vpcf
   uv run voltmod content compile <plugin> particles/<plugin>/<effect> --install client --install server
   ```

4. **Review.** Nothing renders particles outside the game, so the user checks them in game or in
   the Workshop Tools particle editor (`cs2.exe -tools`).
5. **Wire.** `runtime.Entities.SpawnParticle(effect, origin, angles)` starts an effect, and
   removing the entity stops it. Keep a loop's `EntityRef` and remove it with its owner. Give a
   one-shot `RemoveAfter(seconds)`, longer than its longest particle life. Precache every `.vpcf`
   the plugin spawns; children load with it. In Stronghold, `Loop` in
   `StructureAssets` loops at a structure's origin.

- **Textures:** use the game's own, such as `materials/particle/particle_glow_01.vtex` (soft
  glow), `beam_hotwhite.vtex` (streaks) or `sparks/sparks.vtex`. `uv run modelkit particles textures <word>`
  lists them.
- **Schema dump:** the field checks read `references/swiftlys2`, which is local only. Without it,
  `modelkit particles check` stops with `no schema dump`; compile unchecked then.
- **On an existing model:** measure the point in Blender, from the `.blend` or
  `session.import_dmx`, and spawn the effect at the prop's origin plus that offset, turned by its
  yaw (Stronghold's `OffsetByYaw`). The effect won't follow a moving part; animate a glowing part
  for that.
