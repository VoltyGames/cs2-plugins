#include "FunMode.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Events/EventTypes.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <concepts>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <variant>

namespace AdminSystem::Fun
{

static constexpr std::string_view KnifeT = "weapon_knife_t";
static constexpr std::string_view KnifeCT = "weapon_knife";

FunMode::FunMode(VoltMod::Runtime& runtime) : _rt(runtime), _overrides(runtime.ConVars)
{
    ResolveConVars();

    auto& events = _rt.GameEvents;

    _subs.Add(events.On<VoltMod::RoundStart>([this](const VoltMod::RoundStart&) { ApplyRoundStart(); }));

    // Apply round rules to late joins.
    _subs.Add(events.On<VoltMod::PlayerSpawn>([this](const VoltMod::PlayerSpawn& e) {
        if (e.Slot >= 0 && _state.IsOn(Toggle::KnifeRound))
        {
            GiveKnifeOnly(e.Slot);
        }
    }));
}

// Restores changed convars when the plugin unloads.
FunMode::~FunMode() = default;

bool FunMode::Flip(Toggle toggle)
{
    const bool on = _state.Flip(toggle);

    if (toggle == Toggle::KnifeRound)
    {
        ApplyRoundStart();  // Also update players already alive.
    }
    else
    {
        ApplyOverrides();
    }

    return on;
}

void FunMode::ClearAll()
{
    _state.Clear();
    ApplyOverrides();
}

void FunMode::ApplyRoundStart()
{
    // Map changes can reset convars, so reapply active toggles each round.
    ApplyOverrides();

    if (!_state.IsOn(Toggle::KnifeRound))
    {
        return;
    }

    for (auto* player : _rt.Players.All())
    {
        if (player)
        {
            GiveKnifeOnly(player->Slot());
        }
    }
}

void FunMode::ResolveConVars()
{
    for (const auto& row : ToggleConVars)
    {
        const std::string name(row.Name);

        // Only headshot-only is bool; Find rejects a mismatched engine type.
        if (auto number = _rt.ConVars.Find<float>(name))
        {
            _handles.push_back({.Owner = row.Owner, .OnValue = row.OnValue, .Handle = std::move(*number)});
        }
        else if (auto flag = _rt.ConVars.Find<bool>(name))
        {
            _handles.push_back({.Owner = row.Owner, .OnValue = row.OnValue, .Handle = std::move(*flag)});
        }
        else
        {
            VoltMod::Log::Warn("Fun mode: convar '{}' unusable ({}); the toggle that drives it is inert.", name,
                               flag.error().Detail);
        }
    }
}

void FunMode::ApplyOverrides()
{
    for (auto& handle : _handles)
    {
        const bool on = _state.IsOn(handle.Owner);
        std::visit(
            [&](auto& convar) {
                if (!on)
                {
                    _overrides.Restore(convar);
                    return;
                }
                // Headshot-only is the sole bool setting.
                if constexpr (std::same_as<std::remove_cvref_t<decltype(convar)>, VoltMod::ConVar<bool>>)
                {
                    _overrides.Set(convar, handle.OnValue != 0.0f);
                }
                else
                {
                    _overrides.Set(convar, handle.OnValue);
                }
            },
            handle.Handle);
    }
}

void FunMode::GiveKnifeOnly(int slot)
{
    const VoltMod::Pawn pawn = _rt.Entities.Pawn(slot);
    if (!pawn.IsAlive())
    {
        return;
    }

    pawn.StripWeapons(false);
    pawn.GiveItem(pawn.TeamNum() == VoltMod::Team::T ? KnifeT : KnifeCT);
}

}  // namespace AdminSystem::Fun
