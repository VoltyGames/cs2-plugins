---
name: deploy-test
description: Build the Linux plugins (and the voltmod checkout when it has changes) in a local Docker copy of the CI container and deploy them straight to a remote server, skipping the voltmod release -> CI -> Deploy pipeline. Use for "quick deploy", "deploy to the test server", "try it on prod", "test this on panel-a/box-a", "skip the pipeline".
argument-hint: "[server-id] (default: panel-a)"
---

# Quick deploy for testing

Skips the release tag, relock and Deploy workflow (~20 min): build the `.so` files locally, stage
`build/package/`, and run the same `deploy push` as CI. Nothing is committed. The server runs
uncommitted binaries until the next Deploy workflow; a change that tested well still ships through
`commit` and, for voltmod, `release`.

## 1. Build

Needs Docker Desktop. Run in the background; the first run compiles every dependency.

```bash
uv run python .claude/skills/deploy-test/scripts/linux_build.py [--test] [--framework auto|checkout|locked] [--rebuild-image]
```

`--framework auto` (default) links the `voltmod` checkout when it is dirty or not at the `v<version>`
tag `conan.lock` pins, else the locked release; the first output line says which. `locked`
reproduces what CI would ship. The host always ships with the plugins.

State lives in the Docker volumes `cs2-plugins-linux-cache` (Conan, ccache, venvs),
`cs2-plugins-linux-build` and `cs2-plugins-linux-framework`, so reruns are incremental. The
container has its own Conan home; the Windows editable and `conan.lock` stay untouched.

## 2. Deploy

Target: the skill argument, else `panel-a`; an id from `deploy/inventory.yml` with
`deploy/secrets/<id>/.env`. Always pass `--server`, or every enabled server is deployed.

```bash
uv run poe rcon "status" --server <id>              # the deploy restarts the server
uv run poe deploy push --server <id> --dry-run
uv run poe deploy push --server <id>
```

`panel-a` is live: if `status` lists human players, stop and ask before the real push.

## 3. Verify

After about a minute of boot:

```bash
uv run poe rcon "volt list" --server <id>
```

`volt list` must list every plugin of the instance; an unknown command means the host did not
load. One missing after a framework change means the host and plugins came from different builds
(its refusal names both VoltMod versions): rebuild and redeploy. Each line shows the commit the
plugin was built from, so a stale binary is visible there too. Then test the behaviour with `rcon-debug`.

## Failures

- `docker: error during connect`: Docker Desktop is not running.
- A mis-cased include compiles here (the bind mount is case-insensitive); CI still rejects it.
- `locked` cannot resolve `voltmod/<version>#<revision>`: the lock names an unreleased local
  relock. Use `--framework checkout`.
- Toolchain changed (compiler, uv): `--rebuild-image`.
- Wedged build tree: `docker volume rm cs2-plugins-linux-build cs2-plugins-linux-framework`.

## Report

Framework linked, server deployed, the `volt list` response, and that the server now runs
uncommitted binaries.
