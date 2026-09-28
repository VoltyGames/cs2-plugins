# Main menu

The meat.gg hub menu. `!menu` opens a tabbed menu that links to stats, VIP, the admin panel, the
website and other plugins' menus. The last tab is always Settings, where each player picks their
language for every VoltMod plugin.

The Panorama layout ships in the meatgg workshop addon, together with admin-system's menu, the rank
icons and Stronghold's content. Clients that do not have the addon yet get the same menu as center
HTML.

## Commands

| Command | Who | What it does |
| --- | --- | --- |
| `!menu`, `!m` | Everyone | Open the main menu |

## Configuration

Settings are in `addons/voltmod/plugins/main-menu/configs/settings.jsonc` on the server.

| Setting | Default | Purpose |
| --- | --- | --- |
| `plugin.locale` | `ru` | Server language; a player's pick in the Settings tab wins |
| `addonId` | `0` | The workshop addon every connecting client downloads; 0 requires none |
| `menu.panorama` | `true` | Draw the Panorama layout; `false` uses center HTML for everyone |
| `tabs` | stats, shop, VIP, admin, skins, clans, rules | Up to 7 tabs, drawn before Settings |

Each tab has a `label`, an `icon` and a list of `entries`. A label is a translation key, or literal
text when no translation has that key. Icons are `stats`, `shop`, `vip`, `admin`, `skins`,
`clans`, `rules` and `site`.

An entry's `kind` sets what it does:

| Kind | Field | What it does |
| --- | --- | --- |
| `command` | `command` | Runs a console command as the player, such as `mm_lvl` for a legacy plugin's menu |
| `link` | `url` | Prints the URL to the player's chat |
| `section` | `section` | Opens another VoltMod plugin's menu; hidden while that plugin is not loaded |

Sections come from plugins that publish a `Contracts::IMenuSection` (see
[contracts](../contracts/README.md)): `admin` and `report` from admin-system, `stronghold` from
stronghold. An entry with an unknown kind or an empty target is dropped and logged when the
settings load.

Player-facing text is in `translations/`.

## Panorama

`panorama/screens/` holds the menu screen. `panorama/templates/meatgg/` is the meat.gg brand kit
(theme, controls, home and menu styles) that other plugins' screens use as well.

```bash
uv run poe panorama            # render, compile and install into your client
uv run poe meatgg-addon        # build the meatgg addon: every screen plus Stronghold's content
```

For shared build commands, see the [repository README](../../README.md).
