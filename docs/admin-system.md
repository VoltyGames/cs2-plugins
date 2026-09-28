# Admin system

Deployer-facing reference for the admin-system plugin: permissions, the
database it owns, and what changes when several servers share one database. For
the full command and menu listing, see the
[plugin README](../plugins/admin-system/README.md). For build and deploy
mechanics, see [Local development](local-development.md) and
[Deployment](../deploy/README.md).

## Configuration

Runtime settings live in `addons/voltmod/plugins/admin-system/configs/settings.jsonc`. The file
is JSONC, so comments are allowed. The loader ignores both unknown and missing keys, which is
why a retired setting needs no config migration and a missing list falls back to the built-in
defaults.

| Section | Purpose |
| --- | --- |
| `plugin` | Translation file to use, without `.json` |
| `server` | This server's `tag` and display `name` in the shared database |
| `database` | Backend `driver` (`postgres`, `mariadb`, `sqlite`), host, credentials, `sslMode` |
| `punishments` | Ban defaults, warning threshold, presets |
| `abuseProtection` | Sliding-window thresholds that auto-freeze an admin |
| `chat` | Punishment broadcasts and admin chat tagging |
| `reports` | Player report reasons, cooldowns, and duplicate suppression |
| `cheatCheck` | Cheat-check mode and the link or room API behind it |
| `maps` | Maps admins may switch to |
| `weapons` | Weapons the Player Actions > Give weapon menu offers |

A mistyped value fails the whole load; a malformed entry inside a list
(a punishment template, a report reason) is logged and skipped so one typo
cannot take moderation offline.

### Map list

`maps.cycle` is the list of maps admins may switch to. The engine exposes no
usable list of its own, so this is the only source. Leaving it out (or having
every entry skipped) falls back to the built-in active duty group rather than
opening an empty map list.

```jsonc
"cycle": [
  { "name": "de_dust2", "displayName": "Dust II" },
  // A non-zero workshopId addresses a workshop map by published-file id.
  { "name": "surf_utopia", "workshopId": 3070563536 }
]
```

`displayName` is the label the map list shows; it falls back to `name`.

Map control is menu-only. Map & Vote picks the verb first - Change map (with a
confirmation, since it ends everyone's round), Set as next map, or Put to vote -
and each opens the same cycle list. Change map and Set as next map need
`admin.map`, Put to vote and Cancel vote `admin.vote`; a row the admin lacks the
permission for is not drawn at all. Cancel vote stays visible and grays itself
while no vote is running, since the tab's rows are fixed once it opens.

Plain map names are checked against the engine at load, and one it cannot load
is logged there rather than failing when an admin picks it. Workshop maps are
not checked, because they are addressed by id and are not mounted yet.

### Weapon list

`weapons.menu` is what Player Actions > Give weapon offers. `item` is the entity
classname; an entry not starting with `weapon_` is skipped, since it would
otherwise reach the engine as an arbitrary entity. `name` is the menu label and
falls back to `item`. Like `maps.cycle`, an absent or fully-skipped list falls
back to the built-in defaults.

```jsonc
"menu": [
  { "name": "AK-47", "item": "weapon_ak47" }
]
```

The same menu offers a random pick from the list and a Strip weapons entry.
All three need `admin.weapon`.

Giving a weapon the target's team cannot buy works: the server retries once with
the pawn briefly flipped to the other team, then puts it back. A refusal the
retry cannot fix is reported to the admin who clicked.

### Round Modes

Round Modes is a set of server-wide round modifiers, toggled from the Round
Modes tab. Each entry shows its current state, and Clear all turns everything
off. The tab needs `admin.fun_mode`.

| Modifier | Effect |
| --- | --- |
| Low gravity | Drops `sv_gravity` for everyone |
| Headshot only | Only head hits deal damage |
| Knife round | Strips weapons and gives a knife on spawn |
| One-hit kill | Any hit kills outright |

The damage toggles drive the engine's own rules - `mp_damage_headshot_only` and
the four `mp_damage_scale_*` multipliers - rather than the damage hook, which
can read a hit but cannot block or resize one. With both on, only head shots
land and the first one kills.

Every convar a toggle takes over is snapshotted on the way up and put back on
the way down, so the server keeps its own values. Turning low gravity on
snapshots the live `sv_gravity`; turning it off - or Clear all, or unloading the
plugin - restores it, so a server running `sv_gravity 600` keeps it. A server
that never enables a toggle is never written to at all. The toggles are also
re-applied at each round start, because the engine resets convars around a map
change.

### Map vote

`maps.vote` controls the yes/no vote an admin opens from Map > Put to vote.
Players answer through the game's own vote panel, so the plugin keeps no tally
of its own - the engine collects the ballots.

```jsonc
"vote": {
  // Share of the ballots cast that must be yes; a majority of it is required.
  "successRatio": 0.6,
  // How long the panel stays open.
  "durationSec": 20
}
```

Judged on the ballots actually cast, not on everyone connected, so abstaining is
not a no. A passing vote queues the map for the end of the round rather than
cutting the round short. Cancel running vote calls a vote off early. Only one
vote runs at a time, and both entries need `admin.vote`.

## Permissions

Permissions are names stored as JSON arrays in `admins.permissions` and
`admin_groups.permissions`, for example `'["admin.kick", "admin.ban"]'`. An
admin holds the union of their own permissions and those of every group granted
to them. `*` grants everything, and `admin.*` grants every `admin.` permission.

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
| `admin.map` | Change map and queue the next map (Map menu) |
| `admin.weapon` | Give and strip weapons |
| `admin.fun_mode` | Round Modes server-wide modifiers |
| `admin.vote` | Start and cancel map votes (Map menu) |
| `*` | Root access |

Migration `0003_permission_names` converts the old flag letters to these names.

Immunity is separate from permissions and gates punishments only: a kick, ban, mute,
warning or admin freeze needs immunity strictly higher than the target's. Actions and
effects - slay, teleport, health, fun and the rest - are open to any admin holding the
permission, whatever rank the target holds. Immunity comes from the admin's groups;
`admin_groups.immunity` is the only place it is set. `!admin` needs no permission, but
the caller must be a registered admin, and each menu category is still gated individually.

The admin menu draws on either of two surfaces, decided per player when the menu
opens. Rows, flows and callbacks are the same on both.

Center HTML is the default. It needs nothing on the client, and is read with
W/S/A/D/E/R. Turn on `menu.panorama` in `configs/settings.jsonc` and admins get the
clickable Panorama menu instead: eight rows a page, a tab strip over the top-level
categories, a pager, toggle switches, value steppers and a chat-prompt panel.

Either way the client needs the compiled `admin_menu` layout on disk, and there are
two ways to get it there.

**Testing against your own client.** Leave `addonId` at 0 and compile the
layout into your client by hand. Nothing is downloaded and nobody else can see the
menu.

```bash
uv run poe panorama                              # render, compile, install into your client
uv run poe run admin-system  # then set menu.panorama in the server's copy
```

Reconnect after compiling; the client reads the layout at load.

**Serving it to everyone.** The layout ships in the meatgg workshop addon, together
with the main-menu screens, the rank icons and Stronghold's content. Put the
addon's id in the top-level `addonId`; the plugin then requires it of every
connecting client, and an admin who does not have it yet keeps center HTML. For
prod the id is set in `plugins.admin-system.settings` in `deploy/inventory.yml`.

The layout is this plugin's own, under `panorama/screens/admin_menu.*`, built from
the framework's block library and coloured from meat.gg's palette. To publish a
change:

1. Build the addon without touching your client: `uv run poe meatgg-addon`
2. Open meatgg in the CS2 Workshop Tools, then the Workshop Manager, and update the
   item. It must stay Public or Unlisted; a private item does not download for anyone else.

Before testing the download, delete the loose files `uv run poe panorama` copied
into your client's `game/csgo/panorama/`, or the client keeps using them.

The player is frozen while a menu is open either way, so browsing does not also
walk them around.

## Database

`database.driver` in `settings.jsonc` picks the backend: `postgres` (default),
`mariadb`, or `sqlite` (bundled, no server to run). The `database` section of
`configs/settings.jsonc` lists every key, including `path` (the sqlite file) and
`connectTimeoutSec`.

The plugin owns its schema. `migrations/NNNN_name.sql` holds one
dialect-free file per change, and the plugin applies them in filename order at
load, substituting the handful of spellings the backends disagree on. To apply
them by hand, render them for your driver first:

```bash
uv run voltmod database sql migrations --driver postgres | psql -d admin_system
uv run voltmod database sql migrations --driver mariadb  | mariadb admin_system
uv run voltmod database sql migrations --driver sqlite   | sqlite3 admin-system.sqlite
```

Seed the first admin the same way, after putting your SteamID64 in the file:

```bash
uv run voltmod database sql database/seed-admin.sql --driver postgres | psql -d admin_system
```

`admins.groups` and `admin_groups.inherits` hold a JSON array as text (for
example `'["super_admin"]'`) on every backend, not a native array column.
Anything else reading those two columns directly, such as the website, has to
parse JSON.

| Table | Holds |
| --- | --- |
| `admins` | Admin records, permissions, and freeze state |
| `admin_groups` | Named permission and immunity bundles |
| `admin_server_groups` | Which groups an admin holds on which server tag |
| `admin_activity` | Audit trail of every punishment an admin issued |
| `players` | Seen players, names, and IP addresses |
| `punishments` | Bans, voice mutes, text mutes and warnings, active and lifted, told apart by `kind` |
| `servers` | Registered server tags and display names |
| `player_reports` | Reports awaiting an external moderation service |

Gameplay decisions read in-memory caches, not the database, and the writes ride
an async worker. Editing rows directly therefore has no effect until the caches
are rebuilt, so run `!admin_reload` afterwards.

## Multiple servers on one database

Several servers may share a database. `server.tag` is the stable per-server
identity that keeps them apart, so it must be unique and must not change once
grants reference it.

- Punishments are network-wide. A ban issued anywhere applies everywhere.
- Admin grants are per-server through `admin_server_groups`, keyed by
  `server.tag`. An admin can be root on one server and unprivileged on another.
- Abuse-protection windows and admin freezes are network-wide, so an admin
  frozen on one server is frozen on all of them.

Give each server its own tag before its first start. Changing a tag later
orphans every grant that referenced the old one.

## Troubleshooting

### Admin changes made in SQL have no effect

Gameplay reads caches. Run `!admin_reload`, or restart the server.

### The plugin loads but no commands work

Check the load report in the server console and run `admin_status`. A failed
`Database` stage skips the `Admins` stage, leaving nobody holding any permission.

### Grants disappeared after a config change

`server.tag` changed. Restore the previous tag, or repoint the rows in
`admin_server_groups` at the new one.
