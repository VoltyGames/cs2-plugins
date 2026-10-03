#pragma once

#include "ModeRules.hpp"
#include "Scoreboard.hpp"

#include <VoltMod/Api.hpp>

namespace Deathmatch
{

struct App final : VoltMod::Plugin
{
    explicit App(VoltMod::Runtime& runtime) : Plugin(runtime) {}

    bool Load() override
    {
        Rules.CheckGameMode();
        Rules.Apply();
        return true;
    }

    ModeRules Rules{Runtime};
    Scoreboard Score{Runtime};
};

}  // namespace Deathmatch
