#pragma once

#include <VoltMod/App/Config.hpp>

namespace Deathmatch
{

/** Root of settings.jsonc. The game rules live in configs/deathmatch.cfg. */
struct Settings
{
    VoltMod::StandardPluginSettings plugin;
};

using ConfigManager = VoltMod::Options<Settings>;

}  // namespace Deathmatch
