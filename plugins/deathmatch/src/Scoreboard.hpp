#pragma once

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Signals/Subscription.hpp>
#include <VoltMod/Core/Signals/Subscriptions.hpp>

namespace Deathmatch
{

/** Keeps each player's score equal to their kills and drops the game's "N points for..." lines. */
class Scoreboard
{
public:
    explicit Scoreboard(VoltMod::Runtime& runtime);

private:
    void SyncScores();

    VoltMod::Runtime& _runtime;
    VoltMod::Subscription _pendingSync;
    VoltMod::Subscriptions _subs;
};

}  // namespace Deathmatch
