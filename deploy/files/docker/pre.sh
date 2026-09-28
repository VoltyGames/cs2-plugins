#!/usr/bin/env bash
set -euo pipefail

Root="/home/steam/cs2-dedicated"
Csgo="$Root/game/csgo"
AddonsSrc="/home/steam/plugin-bundles/addons"

if [[ ! -d "$Csgo" ]]; then
    echo "CS2 game directory is not present yet: $Csgo" >&2
    exit 0
fi

if [[ -d "$AddonsSrc" ]]; then
    mkdir -p "$Csgo/addons"
    cp -a "$AddonsSrc/." "$Csgo/addons/"
fi

# The engine starts the host through this loader; without it nothing the deploy shipped loads.
if [[ ! -f "$Csgo/addons/voltmod/bin/linuxsteamrt64/libserver_valve.so" ]]; then
    echo "ERROR: no voltmod host in $Csgo/addons; deploy the host together with the plugins" >&2
    exit 1
fi

if [[ -f "$Csgo/gameinfo.gi" ]] && ! grep -q 'csgo/addons/voltmod' "$Csgo/gameinfo.gi"; then
    awk '
        !done && $0 ~ /[[:space:]]Game[[:space:]]+csgo[[:space:]]*$/ {
            match($0, /^[[:space:]]*/); indent = substr($0, 1, RLENGTH)
            printf "%sGame\tcsgo/addons/voltmod\n", indent
            done = 1
        }
        { print }
    ' "$Csgo/gameinfo.gi" > "$Csgo/gameinfo.gi.tmp"
    mv "$Csgo/gameinfo.gi.tmp" "$Csgo/gameinfo.gi"
    if ! grep -q 'csgo/addons/voltmod' "$Csgo/gameinfo.gi"; then
        echo "WARNING: gameinfo.gi patch did not take (format changed?); voltmod will NOT load" >&2
    fi
fi
