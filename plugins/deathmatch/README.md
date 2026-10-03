# Deathmatch

Valve's deathmatch, the way the official servers run it:

- Players respawn at random spots, away from live players and out of their sight, with the stock respawn sound.
- The buy menu is free, and there is ghost time after each spawn.
- The match runs on a timer.

The plugin turns off bonus weapon rounds and bonus points, so the scoreboard's kills are what count.
Valve's mode does the rest; the plugin only applies `configs/deathmatch.cfg` on top of it.

## Getting started

Start the server in deathmatch mode. Without these launch options the plugin logs a warning:

```text
+game_type 1 +game_mode 2
```

Then build and install the plugin:

```bash
uv run poe run deathmatch
```

## Rules

The server's copy is `addons/voltmod/plugins/deathmatch/configs/deathmatch.cfg`. It is created on the
first install, and later installs never overwrite it. The plugin runs it on load and on every map
start, after Valve's `gamemode_deathmatch.cfg`.

| Line | Default | What it does |
| --- | --- | --- |
| `mp_teammates_are_enemies`, `mp_solid_teammates` | `1` | Free-for-all; set both to `0` for team deathmatch |
| `mp_roundtime`, `mp_timelimit` | `10` | Match length in minutes; keep them equal so the match ends when the clock does |
| `mp_respawn_immunitytime` | `10` | Ghost time after a spawn, in seconds; firing ends it early |
| `mp_randomspawn`, `mp_randomspawn_los`, `mp_randomspawn_dist` | `1` | Random spawns away from live players and out of their sight |
| `mp_dm_time_between_bonus_min`, `_max`, `mp_dm_bonus_percent` | `99999`, `0` | No bonus weapon rounds and no bonus points |

Add any other convar line to the file to change it for deathmatch only.
