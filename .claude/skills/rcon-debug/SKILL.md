---
name: rcon-debug
description: Drive a live CS2 server over RCON to test plugin behaviour without a deploy cycle - reads/writes convars, runs plugin commands, reads server logs. Use for "test it on the server", "check it live", "why is X not working in game", "run this on box-a", or any server-side behaviour question.
---

# Debug over RCON

Confirm a hypothesis on the server before writing a fix.

## Local server

```bash
uv run python .claude/skills/rcon-debug/scripts/local.py [--start] "volt list" "status"
```

Reads `.env`, finds the adapter CS2 bound (often a virtual one, not loopback), and prints each
response under `=== <command> ===`. `--start` launches `cs2.exe` detached with `-condebug` when
nothing listens, and waits for RCON. The log, VoltMod lines included, is then
`<CS2_SERVER_PATH>/game/csgo/addons/voltmod/console.log` (`addons/metamod/` when Metamod is
installed); `poe serve` writes no file. Stop the server with the `quit` command. Anything that needs
a player in game waits for the user (`connect localhost:27015` in their client).

## Remote server

```bash
uv run poe rcon "<command>" ... [--server <id>] [--instance <name>]
```

Address and password come from `deploy/inventory.yml` and `deploy/secrets/<id>/.env`; the flags are
optional with one enabled server and instance. Logs:

- Panel server (no shell): the panel console, or
  `deploy.cli.find_deployer('<id>').api.read('/game/logs/console_<date>.log')`.
- Docker host: `ssh -i <SSH_KEY_FILE> -o IdentitiesOnly=yes steam@<host>` (both in the inventory and
  `.env`), then `docker logs <server-id>-cs2-<instance>`. Binaries are under
  `/home/steam/cs2/deploy/instances/<instance>/bundles/addons/voltmod/plugins/<plugin>/`.

## Check the binary first

Most "feature is missing" reports are a stale binary. `volt list` shows only the `plugin.json`
version, so compare the installed `<name>.dll`/`.so` mtime with the commit that added the feature.
Older: rebuild instead of reading code.

## What the console reaches

Only commands built with `.ServerOnly()` or `.Anywhere()`, with no permission check; chat-only
commands need a player. List them:

```bash
grep -rn -A3 '\.Add("' plugins --include=*.cpp | grep -B3 -E '\.(ServerOnly|Anywhere)\(' | grep '\.Add("'
```

Engine: `status`, `<convar>` to read, `<convar> <value>` to set, `mp_restartgame 1`.

## Rules

- Check `status` for human players first. `mp_restartgame`, map changes and `sv_cheats` hit
  everyone: ask before using them on a populated server. Restore every convar you change.
- Never print RCON passwords, SSH keys or the `cs2.exe` command line.

## Bots, for headless repros

Bots drive damage, movement and per-tick hooks with nobody connected:

```text
sv_hibernate_when_empty 0; bot_join_after_player 0; bot_quota_mode fill; bot_quota 10
bot_difficulty 3; mp_freezetime 3; mp_roundtime 60; mp_roundtime_defuse 60; mp_warmup_end; mp_restartgame 1
```

`bot_allow_*` convars pick their weapons. `Start-Sleep` is blocked here: poll inside one script, or
Bash `run_in_background` with an `until` loop.

## Probing a path the console cannot reach

Don't script a chat menu. Hard-code the effect on an unconditional trigger, install, watch, remove:

```cpp
// PROBE: every chest hit, regardless of toggles.
if (view.Hitbox == VoltMod::HitGroup::Chest)
    view.Suppress = true;
```

Log the state you mean to change and compare consecutive lines: a plausible mechanism can be a
no-op (writes to `CTakeDamageInfo` under a `SUPERCEDE` changed nothing; only per-hit hp showed it).

## Report

Quote the actual responses, name the instance, list every convar changed and restored, and for a
repro say how many events you observed; two is not a result.
