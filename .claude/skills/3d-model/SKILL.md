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
| `scripts/check.py` | Checks the tools outside Blender |
| `scripts/compile.py` | Compiles one model or particle folder and installs it |
| `scripts/particles.py` | Checks `.vpcf` field names; lists a class's fields and the game's particle textures |
| `scripts/modelkit/` | The helpers you run inside Blender, below |
| `examples/jump_pad.py` | A skinned, animated prop. Read it before building one |
| `examples/teleporter.py` | Glow, team colour and FX animations. Read it before adding FX |

| `modelkit` module | For |
| --- | --- |
| `session` | Status, scenes, opening models, cleanup |
| `surfaces` | Textures and preview materials |
| `shapes` | Mesh parts |
| `objects` | Finishing, joining and editing parts |
| `rig` | Skeleton and actions |
| `preview` | Renders and the user's viewport |
| `source2` | DMX export and the `.blend` |
| `modeldoc` | `.vmat`, `.vmdl` and `.vpcf` writers; also runs without Blender |

One Blender unit is one Source unit; +X is forward and +Z is up. A player is 32 × 32 × 72 units,
with eyes at 64.

## 1. Check the tools

```bash
uv run python .claude/skills/3d-model/scripts/check.py <plugin>
```

Then load the kit in Blender:

```python
import sys
sys.path.insert(0, r"<repo>/.claude/skills/3d-model/scripts")
import modelkit
modelkit.reload()
from modelkit import session, surfaces, shapes, objects, rig, preview, source2, modeldoc
result = session.status()
```

Stop and tell the user if:

- Blender or its MCP doesn't answer.
- `source_tools_enabled` is false.
- `check.py` reports MISSING. Codex only matters for new textures, and a running CS2 only blocks
  installing.

If the user has unsaved changes, work only in the model's own scene.

## 2. Pick the path

| Situation | Start with |
| --- | --- |
| A new model | Step 3, then `session.scene(name, "models/<plugin>/<model>/")` |
| A model with a `.blend` | `session.open_model(<blend>)`, which opens every part's scene |
| A model with DMX files only, such as a stand-in | `session.import_dmx(scene, folder, meshes, animations)`; check it, then `source2.remember(...)` |
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
- **Size:** the scale, placement box, trigger radii (the jump pad's `Launcher`) and offsets
  measured on the mesh, such as muzzles and each part's `At`.
- **Names:** attachments, animations, material groups (`Skin`) and bones.
- **Assets doc:** the plugin's `docs/assets.md` has the addon layout and licence status.

## 4. Textures

List `~/.codex/generated_images/` before the first run, so cleanup knows which folders are new.
Then run Codex in the background while you work:

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
  and repoint a renamed material with `objects.replace_material`. To only resize, use the
  plugin's scale.
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

## 6. Animate

`rig.skeleton` makes the bones and skins the mesh by vertex group. `rig.animate` records an action
from per-bone `(frame, move, turn)` keys at 30 fps, relative to rest. `rig.eased` fills in the
frames between keys without overshoot. `source2.remember` saves the export settings in the
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
source2.export(scene, model_dir)                        # meshes, hull, one DMX per action
source2.save_blend(scenes, model_dir + "/<folder>.blend")  # every part's scene; Git LFS, not the compile
modeldoc.write_vmat(...)  # only for new or changed materials
modeldoc.write_vmdl(...)  # only when meshes, animations, groups or attachments change
```

Stop the CS2 server and client first; installing into a running game fails.

```bash
uv run python .claude/skills/3d-model/scripts/compile.py plugins/<plugin>/addon models/<plugin>/<model> --install client server
```

- `export` refuses `.001` materials and leaves object references stale, so look objects up by
  name afterwards.
- `compile.py` mirrors the folder into the Workshop Tools content folder, recompiles it from
  scratch and copies the result to each install target.

## 9. Wire it into the plugin

- Point the plugin at the `.vmdl`, and update the scale, placement box, trigger radii and measured
  offsets. In Stronghold, `Scale` in `StructureAssets` resizes the model, collision and animation
  without a recompile.
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
- **Model folder:** `compile.py --prune` deletes sources nothing names, such as replaced textures.
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

1. **Write** each effect into `<addon>/particles/<plugin>/<effect>/` with `modeldoc.write_vpcf`,
   built from `modeldoc.op(...)` operators. A team variant is its own file; a part several effects
   share is a child.
2. **Check the field names.** `resourcecompiler` silently drops fields it doesn't know, so a typo
   compiles into an effect without that setting. `particles.py fields <class>` prints the real
   names: `C_INIT_RandomLifeTime` takes `m_fLifetimeMin`, not `m_flLifetimeMin`.
3. **Compile and install.** `compile.py` runs `particles.py check` first and stops on an unknown
   field:

   ```bash
   uv run python .claude/skills/3d-model/scripts/compile.py plugins/<plugin>/addon particles/<plugin>/<effect> --install client server
   ```

4. **Review.** Nothing renders particles outside the game, so the user checks them in game or in
   the Workshop Tools particle editor (`cs2.exe -tools`).
5. **Wire.** `runtime.Entities.SpawnParticle(effect, origin, angles)` starts an effect, and
   removing the entity stops it. Keep a loop's `EntityRef` and remove it with its owner. Give a
   one-shot `RemoveAfter(seconds)`, longer than its longest particle life. Precache every `.vpcf`
   the plugin spawns; children load with it. In Stronghold, `Loop` in
   `StructureAssets` loops at a structure's origin.

- **Textures:** use the game's own, such as `materials/particle/particle_glow_01.vtex` (soft
  glow), `beam_hotwhite.vtex` (streaks) or `sparks/sparks.vtex`. `particles.py textures <word>`
  lists them.
- **Schema dump:** the field checks read `references/swiftlys2`, which is local only. Without it,
  `compile.py` says so and compiles unchecked.
- **On an existing model:** measure the point in Blender, from the `.blend` or
  `session.import_dmx`, and spawn the effect at the prop's origin plus that offset, turned by its
  yaw (Stronghold's `OffsetByYaw`). The effect won't follow a moving part; animate a glowing part
  for that.
