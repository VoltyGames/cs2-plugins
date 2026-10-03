#pragma once

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Signals/Subscription.hpp>
#include <VoltMod/Core/Signals/Subscriptions.hpp>

namespace Deathmatch
{

/** Runs `configs/deathmatch.cfg` over Valve's deathmatch mode and warns when the server runs another mode. */
class ModeRules
{
public:
    /** Reapplies the rules on every map start: Valve's gamemode cfg resets them on a map change. */
    explicit ModeRules(VoltMod::Runtime& runtime);

    /** Runs the cfg line by line (`exec` reads only csgo/cfg). */
    void Apply();

    /** Logs a warning unless the server runs `game_type 1` / `game_mode 2`. */
    void CheckGameMode();

private:
    VoltMod::Runtime& _runtime;
    VoltMod::Subscription _pendingApply;
    VoltMod::Subscriptions _subs;
};

}  // namespace Deathmatch
