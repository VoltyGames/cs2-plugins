#include "Scoreboard.hpp"

#include <VoltMod/Events/EventTypes.hpp>
#include <string_view>

namespace Deathmatch
{

static constexpr std::string_view PointAward = "#Player_Point_Award_";

Scoreboard::Scoreboard(VoltMod::Runtime& runtime) : _runtime(runtime)
{
    _subs.Add(_runtime.TextMessages.Before += [](VoltMod::TextMessage& text) {
        if (text.Text.starts_with(PointAward))
        {
            text.Blocked = true;
        }
    });
    // The game adds its points after the death event, so the score is set a tick later.
    _subs.Add(_runtime.GameEvents.On<VoltMod::PlayerDeath>([this](const VoltMod::PlayerDeath&) {
        _pendingSync = _runtime.Scheduler.NextTick([this] { SyncScores(); });
    }));
}

void Scoreboard::SyncScores()
{
    for (VoltMod::Player* player : _runtime.Players.All())
    {
        const VoltMod::Controller controller = player->Controller();
        // Every write is networked, so only a changed score is set.
        if (const int kills = controller.ActionTrackingServices().MatchStats().Kills(); controller.Score() != kills)
        {
            controller.SetScore(kills);
        }
    }
}

}  // namespace Deathmatch
