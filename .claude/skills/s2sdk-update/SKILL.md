---
name: s2sdk-update
description: Research the latest upstream s2sdk commits, pin voltmod's s2sdk recipe to them, rebuild and relock, and report what the new headers let the project simplify. Use for "update s2sdk", "what's new in s2sdk", "bump the SDK", "follow upstream s2sdk".
---

# Update s2sdk

The framework builds against the official `alliedmodders/s2sdk` (`cs2` branch) through its own
Conan recipe. A daily bot (`voltmod/.github/workflows/watch.yml`) already bumps the pin and locks it
once CI passes. This skill does the same by hand, and adds the part the bot cannot do: reading what
changed and finding what the framework can now drop or adopt.

## Where things live

| What | Where |
| --- | --- |
| Upstream clone (read-only, never edit) | `references/s2sdk` |
| Recipe pin: version, URL, commit | `voltmod/conan/recipes/s2sdk/conandata.yml` |
| Recipe: headers, libs, protobufs it packages | `voltmod/conan/recipes/s2sdk/conanfile.py` |
| Watcher that writes the pin | `voltmod/tools/release/sdk_updates.py` (`poe release watch`) |
| Framework lock | `voltmod/conan.lock` |
| Plugins lock | `conan.lock` |
| Offsets and signatures the SDK does not cover | `voltmod/gamedata/gamedata.jsonc` |

## 1. See what changed

1. `git -C references/s2sdk fetch` (fetch only, so the clone stays untouched).
2. Read the pinned commit from `conandata.yml`, then list the new commits:
   `git -C references/s2sdk log --format='%h %ad %s' --date=short <pin>..origin/cs2`.
3. Get the size of the change: `git -C references/s2sdk diff --stat <pin> origin/cs2`.
4. If the pin URL is not `alliedmodders/s2sdk`, compare the fork against upstream with
   `gh api repos/alliedmodders/s2sdk/compare/cs2...<owner>:s2sdk:<commit>`. Leave the fork only
   once upstream carries every commit it adds.

## 2. Triage the diff

Read the diff of each touched header, then grep `voltmod/src`, `voltmod/include`, `plugins/` and
`contracts/` for its symbols.

| Upstream change | What it means here |
| --- | --- |
| Renamed member or `m_unkNNN` given a name | Compile break where we use it; rename our side |
| Virtual added, removed or reordered | Every later slot shifts; check `KHook::GetVtableIndex` users and gamedata vtable entries |
| Changed virtual signature | Fix our hook lambdas and `Bindings.hpp` prototypes |
| New struct members or layout | Can replace a gamedata `offsets` entry or a hand-written struct; check `offsetof` first |
| New enum values or defines | Can replace our own magic numbers |
| `#include` with upper case letters | Breaks only on Linux CI |

To check an offset, compile a tiny probe against the built package that prints `offsetof(...)`,
and compare it with `gamedata.jsonc`. Delete the probe afterwards.

## 3. Pin and build

Run every step in the MSVC dev shell (`build-local`), with `VIRTUAL_ENV` cleared inside `voltmod`.

1. In `voltmod`: `uv run poe release watch --package s2sdk`. It writes the upstream tip and the
   next free version into `conandata.yml`.
2. In `voltmod`: `uv run poe release build sdk`. Note the new recipe revision from
   `uv run conan list "s2sdk/<version>#*" -c`.
3. Pin it in `voltmod/conan.lock`: `conan lock remove --requires="s2sdk/*"`, then
   `conan lock add --requires="s2sdk/<version>#<revision>"`, both with
   `--lockfile=conan.lock --lockfile-out=conan.lock`.
4. In `voltmod`: `uv run poe build`, then `uv run poe test`.
5. At the root: pin the same s2sdk (and khook, if voltmod's lock moved it) in `conan.lock` the
   same way.
6. At the root: `uv run conan editable add voltmod`, `uv run poe build`, `uv run poe test`.
7. Check the build really used the new SDK: `PACKAGE_VERSION` in
   `build/windows-msvc-release/generators/s2sdk-config-version.cmake`.

A recipe revision is a hash of the recipe files, so the local revision matches the one CI uploads
as long as `git -C voltmod ls-files --eol conan/recipes` lists no `w/crlf`.

## 4. Report

- The commits picked up, grouped by area, in one line each.
- What broke and how it was fixed.
- Improvement candidates: file, the SDK symbol that replaces it, and the tradeoff. Don't implement
  them unless the user asks.
- Build and test results for both repos, and what is left to ship.

## 5. Ship (only when the user asks)

1. Commit `conandata.yml` and the code fixes in voltmod and push (`commit` skill). The SDK
   workflow publishes the package, then the bot rewrites `voltmod/conan.lock` with the published
   timestamp.
2. Release voltmod (`release` skill) when plugins need the new headers, then relock the root with
   `uv run poe build --relock`.

## Never

- Edit anything under `references/`.
- Upload packages from this machine.
- Commit a root `conan.lock` naming a revision the `volty` remote does not have.
