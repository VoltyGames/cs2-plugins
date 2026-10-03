#include "ModeRules.hpp"

#include <VoltMod/Core/Log.hpp>
#include <string_view>

namespace Log = VoltMod::Log;

namespace Deathmatch
{

static constexpr int DeathmatchType = 1;
static constexpr int DeathmatchMode = 2;

ModeRules::ModeRules(VoltMod::Runtime& runtime) : _runtime(runtime)
{
    _subs.Add(_runtime.Map.Started += [this](std::string_view) {
        CheckGameMode();
        // The engine runs the gamemode cfg after this event, so the rules go in a tick later.
        _pendingApply = _runtime.Scheduler.NextTick([this] { Apply(); });
    });
}

void ModeRules::Apply()
{
    if (auto applied = _runtime.ConVars.ExecuteFile(_runtime.PluginFile("configs/deathmatch.cfg")); !applied)
    {
        Log::Warn("Deathmatch rules not applied: {}", applied.error().Detail);
    }
}

void ModeRules::CheckGameMode()
{
    const auto type = _runtime.ConVars.Find<int>("game_type");
    const auto mode = _runtime.ConVars.Find<int>("game_mode");
    if (!type || !mode)
    {
        Log::Warn("Game mode not checked: {}", !type ? type.error().Detail : mode.error().Detail);
        return;
    }
    if (type->Get() == DeathmatchType && mode->Get() == DeathmatchMode)
    {
        return;
    }
    Log::Warn("The server runs game_type {} / game_mode {}; start it with +game_type {} +game_mode {} for deathmatch",
              type->Get(), mode->Get(), DeathmatchType, DeathmatchMode);
}

}  // namespace Deathmatch
