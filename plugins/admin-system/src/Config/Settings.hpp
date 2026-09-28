#pragma once

#include "Config/AbuseProtectionSettings.hpp"
#include "Config/ChatSettings.hpp"
#include "Config/CheatCheckSettings.hpp"
#include "Config/MapSettings.hpp"
#include "Config/PunishmentSettings.hpp"
#include "Config/ReportSettings.hpp"
#include "Config/ServerSettings.hpp"
#include "Config/WeaponSettings.hpp"

#include <VoltMod/App/Config.hpp>
#include <VoltMod/Database/DatabaseConfig.hpp>
#include <string_view>

namespace AdminSystem::Config
{
using PluginSettings = VoltMod::StandardPluginSettings;

/** The whole of `configs/settings.jsonc`. Each member is one top-level object in the file;
 *  the section headers next to this one document the individual keys. */
struct Settings
{
    PluginSettings plugin;
    ServerSettings server;
    VoltMod::DatabaseConfig database;
    PunishmentSettings punishments;
    AbuseProtectionSettings abuseProtection;
    ChatSettings chat;
    ReportSettings reports;
    CheatCheckSettings cheatCheck;
    MapSettings maps;
    /** The workshop addon every connecting client must download; 0 requires none. */
    uint64_t addonId = 0;
    VoltMod::PanoramaMenuSettings menu;
    WeaponSettings weapons;
};

}  // namespace AdminSystem::Config
