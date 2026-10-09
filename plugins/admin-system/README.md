# Admin system

[![Version](https://img.shields.io/badge/version-1.0.0-7c3aed.svg)](plugin.json)
[![CI](https://github.com/VoltyGames/cs2-plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/VoltyGames/cs2-plugins/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](../../LICENSE)

Database-backed administration for Counter-Strike 2 servers. It includes an in-game panel,
moderation commands, player controls, reports, cheat checks, and permissions that can be shared
across several servers.

<p align="center">
  <img src="../../docs/assets/admin-panel-ui.png" alt="The admin-system Panorama panel open in Counter-Strike 2">
</p>

## Features

| Area | Tools |
| --- | --- |
| Moderation | Kick, ban, unban, voice mute, text mute, warnings, and network-wide enforcement |
| Player control | Slay, teleport, freeze, noclip, team changes, health, armor, speed, size, and bury |
| Effects | Ghost, disco, wallhack, smite, player models, and optional [bhop grants](../bhop/README.md) |
| Server control | Map changes, next-map selection, map votes, weapon management, and round modes |
| Access | Groups, wildcard permissions, immunity, per-server grants, and admin stealth |
| Admin control | Automatic or manual admin freezes, configurable abuse limits, and an audit trail |
| Reports and checks | Player reports and fixed-link, website-room, or player-provided cheat checks |

Database work runs asynchronously. Migrations run on startup, and gameplay checks use in-memory
caches.

## Requirements

- Counter-Strike 2 dedicated server
- VoltMod's `gameinfo.gi` line; see [Install a release](../../README.md#install-a-release)
- PostgreSQL 13+, MariaDB 10.5+, or SQLite (bundled, no server needed)

## Install

1. Extract the release into the server's `game/csgo/` directory.
2. Open `addons/voltmod/plugins/admin-system/configs/settings.jsonc` and configure the
   `database` section.
3. Set a unique, permanent `server.tag` on every server that shares the database.
4. Start the server. The plugin creates or upgrades its tables automatically.
5. Create the first admin. In a source checkout, replace the sample SteamID64 and name in
   [`database/seed-admin.sql`](database/seed-admin.sql), then render the script for your database
   driver. This PostgreSQL example runs from the repository root:

   ```bash
   uv run voltmod database sql plugins/admin-system/database/seed-admin.sql \
     --driver postgres | psql -d admin_system
   ```

6. Restart the server or run `!admin_reload` to load the new admin.

Run `volt list` in the server console after startup. `admin-system` should appear in the loaded
plugin list. If it does not, check the VoltMod log for a configuration or database error.

To apply migrations manually, render
[`migrations/`](migrations/) the same way.

## Permissions

Permissions are names in a JSON array, for example `'["admin.kick", "admin.ban"]'`.
`*` grants every permission and `admin.*` every `admin.` one. Self-targeting
remains available where the action supports it.

| Permission | Access |
| --- | --- |
| `admin.freeze_admins` | Freeze and unfreeze admins |
| `admin.hide` | Hide and player-list commands |
| `admin.kick` | Kick |
| `admin.ban` | Ban |
| `admin.unban` | Unban |
| `admin.mute` | Voice mute, text mute, and warnings |
| `admin.control` | Player controls and cheat checks |
| `admin.fun` | Fun effects: ghost, disco, smite, and size |
| `admin.health` | Health, armor, and godmode |
| `admin.wallhack` | Wallhack |
| `admin.bhop` | Bhop grants |
| `admin.map` | Change map and queue the next map (Map & Vote tab) |
| `admin.weapon` | Give and strip weapons (Player Actions tab) |
| `admin.fun_mode` | Server-wide modifiers (Round Modes tab) |
| `admin.vote` | Start and cancel map votes (Map & Vote tab) |
| `*` | Root access |

`!admin` has no dedicated permission, but the caller must be a registered admin.
A tab or row the admin holds no permission for is not drawn at all, so the panel
shows only what that admin can actually use.

## Commands

Map control, weapons, and the round modifiers are menu-only - `!admin` opens the
panel, and each tab appears only when the admin may use something inside it. The
commands below are the ones with no menu equivalent.

### Moderation and administration

| Command | Permission | Purpose |
| --- | --- | --- |
| `!kick <target> [reason]` | `admin.kick` | Kick a player |
| `!ban <target> <duration> [reason]` | `admin.ban` | Ban a player |
| `!unban <steamid> [reason]` | `admin.unban` | Remove a ban |
| `!voice_mute <target> <duration> [reason]` | `admin.mute` | Mute voice; aliases: `!vmute`, `!mute` |
| `!voice_unmute <target\|steamid>` | `admin.mute` | Restore voice; aliases: `!vunmute`, `!unmute` |
| `!text_mute <target> <duration> [reason]` | `admin.mute` | Block chat; aliases: `!tmute`, `!gag` |
| `!text_unmute <target\|steamid>` | `admin.mute` | Restore chat; aliases: `!tunmute`, `!ungag` |
| `!warn <target> [reason]` | `admin.mute` | Warn a player and apply configured escalation |
| `!admin` | registered admin | Open the menu; alias: `!a` |
| `!who` | `admin.hide` | List players, prefixes, and immunity; alias: `!players` |
| `!hide` | `admin.hide` | Toggle admin stealth |
| `!admin_reload` | `*` | Reload admins, groups, grants, and freezes; alias: `!reload_admins` |

### Admin freezes

| Command | Permission | Purpose |
| --- | --- | --- |
| `!freeze_admin <target\|steamId> [reason]` | `admin.freeze_admins` | Suspend a lower-immunity admin |
| `!unfreeze_admin <steamId\|name>` | `admin.freeze_admins` | Restore a frozen admin |
| `!frozen_admins` | `admin.freeze_admins` | List active freezes |

### Cheat checks and reports

| Command | Permission | Purpose |
| --- | --- | --- |
| `!check <target>` | `admin.control` | Start a cheat check |
| `!cccancel <target>` | `admin.control` | Cancel a check; alias: `!uncheck` |
| `!cc <link>` | none | Let the suspect submit a verification link |
| `!report` | none | Open the report menu; alias: `!r` |

`!report` takes no arguments. The menu resolves the selected player to a
SteamID, so a report cannot land on the wrong player with a similar name.

### Targets and durations

Targets may be `@all`, `@me`, `@!me`, `@t`, `@ct`, `@spec`, `@dead`,
`@alive`, `@bot`, `@human`, `@random`, `@randomt`, `@randomct`, `#slot`,
a SteamID, or a player name. Names resolve by exact match, then prefix, then
substring.

Durations accept values such as `30s`, `5m`, `2h`, `7d`, and `1w`. A bare
number means minutes; `0` and `perm` mean permanent.

## Configuration

Runtime settings live in
[`configs/settings.jsonc`](configs/settings.jsonc). The file controls server
identity, database access, punishment templates, abuse thresholds, reports,
chat, and cheat checks. The shipped defaults include:

- Russian (`ru`) as the default locale.
- A 10-minute abuse window with limits of 5 bans, 10 kicks, 15 mutes, and
  15 warnings.
- A 120-second report cooldown and 1,800-second duplicate-report window.
- Custom report reasons enabled.
- A 120-second cheat-check timeout with automatic kicking enabled.

Cheat checks support `fixedLink`, `websiteAutoRoom`, and `playerProvided`
modes. Website presence polling is optional.

Player-facing messages live under
[`translations/`](translations/). Keep every language file
key-parallel. Reload database-backed admin state with `!admin_reload` after
changing groups, grants, or admins.

## Multi-server setup

Several servers can share one database:

```jsonc
"server": {
  "tag": "server-1",
  "name": "My Community #1"
}
```

Treat `server.tag` as permanent once grants reference it. On startup, the
plugin registers the server and updates `last_seen` every minute.

- `admins.group_id` applies network-wide; an admin holds one group.
- An `admin_server_groups` row replaces that group on one `server.tag`.
- Admin permissions are global; immunity comes from the admin's group.
- Group permissions and immunity apply wherever that group is granted.
- Bans, mutes, and warnings apply across all servers sharing the database.

Example per-server grant:

```sql
INSERT INTO admin_server_groups (admin_steam_id, server_tag, group_id)
VALUES (76561198000000000, 'server-1', (SELECT id FROM admin_groups WHERE name = 'super_admin'))
ON CONFLICT (server_tag, admin_steam_id) DO UPDATE SET group_id = EXCLUDED.group_id;
```

Run `!admin_reload` on affected servers after changing grants.

## Abuse protection

Every kick, ban, mute, and warning is written to `admin_activity`. After each
action, the plugin checks the issuing admin's network-wide totals over the
configured sliding window. Root admins are exempt.

An admin with `admin.freeze_admins` can manually freeze another admin with strictly lower
immunity. Frozen admins keep their database records but lose all permissions
on every connected server until unfrozen. The plugin broadcasts the freeze,
notifies the admin immediately or on connection, and propagates the state to
other servers within about one minute. Existing punishments remain active for
review, and freeze changes are audited.

## Player reports

`!report` opens a WASD menu for player, reason, and confirmation. Players can
keep moving while it is open. Bots, the reporter, and recently reported players
are unavailable.

Cooldown and duplicate checks are enforced throughout the menu flow and again
at confirmation. A failed database write refunds the cooldown. Custom reasons
are limited to 64 characters and stored with the code `other`.

The plugin only inserts reports. An external service owns triage fields such as
`status`, `handled_by`, `handled_at`, and `resolution`.

## Database tables

The main tables are:

- `admins`, `admin_groups`, and `admin_server_groups` for access.
- `servers` for server identity and heartbeats.
- `admin_activity` for the audit trail.
- Punishment tables for network-wide enforcement.
- `player_reports` for external report triage.

For shared build commands, see the [repository README](../../README.md).
