#include "BhopManager.hpp"

#include <VoltMod/Core/Log.hpp>
#include <VoltMod/Core/Text/EnumNames.hpp>
#include <VoltMod/Entities/EntitySystem.hpp>
#include <VoltMod/Events/EventTypes.hpp>
#include <algorithm>
#include <cmath>
#include <mathlib/vector.h>
#include <string_view>
#include <utility>

using VoltMod::MaxPlayers;
using VoltMod::MessageKind;
using VoltMod::Pawn;
using VoltMod::Player;

namespace Log = VoltMod::Log;

namespace Bhop
{

BhopManager::BhopManager(VoltMod::Runtime& runtime, ConfigManager& config)
    : _rt(runtime), _config(config), _conVars(runtime.ConVars)
{
    auto& events = _rt.GameEvents;
    _subs.Add(events.On<VoltMod::PlayerSpawn>([this](const VoltMod::PlayerSpawn& e) { OnPlayerSpawn(e.Slot); }));
    _subs.Add(events.On<VoltMod::PlayerJump>([this](const VoltMod::PlayerJump& e) { OnPlayerJump(e.Slot); }));
    // Map changes can reset gamemode convars.
    _subs.Add(events.On<VoltMod::RoundStart>([this](const VoltMod::RoundStart&) {
        if (_mode == Mode::Enabled)
        {
            _conVars.ApplyGlobal();
        }
    }));

    _subs.Add(_rt.Players.Disconnected += [this](VoltMod::Player& player) { OnPlayerDisconnect(player); });

    // Grants need a post-simulation hop because subtick movement ignores the scoped override.
    _subs.Add(_rt.Scheduler.EveryFrame([this] {
        if (_mode != Mode::Grants)
        {
            return;
        }
        for (int slot = 0; slot < MaxPlayers; ++slot)
        {
            if (_grantedSlots[slot])
            {
                ForceAutoHop(slot);
            }
        }
    }));

    // Forced hops read this every frame.
    if (auto impulse = _rt.ConVars.Find<float>("sv_jump_impulse"))
    {
        _jumpImpulse = std::move(*impulse);
    }
    else
    {
        Log::Warn("sv_jump_impulse unusable ({}); forced hops use the engine default.", impulse.error().Detail);
    }

    RegisterConsoleCommands();
}

void BhopManager::ApplySettings()
{
    const BhopSettings& settings = _config.Get().bhop;

    if (auto parsed = VoltMod::Parse<Mode>(settings.mode))
    {
        _mode = *parsed;
    }
    else
    {
        Log::Warn("Unknown bhop.mode '{}'; falling back to 'enabled'.", settings.mode);
        _mode = Mode::Enabled;
    }

    _conVars.Build(settings);

    // Only grant mode needs per-player movement hooks.
    if (_mode == Mode::Grants && _movementSubs.Empty())
    {
        _movementSubs.Add(_rt.Movement.Before +=
                          [this](int slot, const VoltMod::PlayerInput&) { OnRunCommandPre(slot); });
        _movementSubs.Add(_rt.Movement.After +=
                          [this](int slot, const VoltMod::PlayerInput&) { OnRunCommandPost(slot); });
    }
    else if (_mode != Mode::Grants)
    {
        _movementSubs.Clear();
    }

    if (_mode == Mode::Enabled)
    {
        _conVars.ApplyGlobal();
    }

    Log::Info("Bhop mode: {} ({} convar overrides).", _mode == Mode::Enabled ? "enabled" : "grants", _conVars.Count());
}

void BhopManager::Grant(int64_t steamId, bool enabled)
{
    if (enabled)
    {
        _granted.insert(steamId);
    }
    else
    {
        _granted.erase(steamId);
    }

    Player* player = _rt.Players.BySteamId(steamId);
    if (!player)
    {
        return;
    }

    int slot = player->Slot();
    if (!VoltMod::IsValidSlot(slot))
    {
        return;
    }

    _grantedSlots[slot] = enabled;

    if (_mode == Mode::Grants)
    {
        if (enabled)
        {
            _conVars.ReplicateOverrides(slot);
        }
        else
        {
            _conVars.ReplicateServerValues(slot);
        }
    }

    if (_config.Get().bhop.notifyPlayer)
    {
        _rt.Messages.SendKey(slot, enabled ? "bhop.granted" : "bhop.revoked", {}, MessageKind::Center);
    }
}

void BhopManager::ReloadSettings()
{
    _conVars.Reset();

    if (auto loaded = _config.Reload(); !loaded)
    {
        Log::Warn("bhop_reload: {}; keeping previous values in memory.", loaded.error().Detail);
        return;
    }

    ApplySettings();

    // Refresh prediction values for granted clients.
    if (_mode == Mode::Grants)
    {
        for (int slot = 0; slot < MaxPlayers; ++slot)
        {
            if (_grantedSlots[slot])
            {
                _conVars.ReplicateOverrides(slot);
            }
        }
    }

    Log::Info("bhop_reload: settings re-applied.");
}

void BhopManager::OnPlayerDisconnect(Player& player)
{
    // Grants do not survive reconnects.
    _granted.erase(player.SteamId());

    int slot = player.Slot();
    if (VoltMod::IsValidSlot(slot))
    {
        _grantedSlots[slot] = false;
        _lastJump[slot] = {};
    }
}

void BhopManager::OnRunCommandPre(int slot)
{
    const bool granted = VoltMod::IsValidSlot(slot) && _grantedSlots[slot];
    if (_mode == Mode::Grants && granted)
    {
        _conVars.HoldRaw();
    }
}

void BhopManager::OnRunCommandPost(int /*slot*/)
{
    _conVars.ReleaseRaw();
}

bool BhopManager::IsActiveSlot(int slot) const
{
    if (!VoltMod::IsValidSlot(slot))
    {
        return false;
    }
    return _mode == Mode::Enabled || _grantedSlots[slot];
}

void BhopManager::OnPlayerJump(int slot)
{
    const HopBoostSettings& boost = _config.Get().bhop.hopBoost;
    if (!boost.enabled || !IsActiveSlot(slot))
    {
        return;
    }

    auto now = std::chrono::steady_clock::now();
    auto last = _lastJump[slot];
    _lastJump[slot] = now;

    bool chained = last.time_since_epoch().count() != 0 && now - last <= std::chrono::milliseconds(boost.chainWindowMs);
    if (!chained)
    {
        return;
    }

    Pawn pawn = _rt.Entities.Pawn(slot);
    if (!pawn)
    {
        return;
    }

    Vector velocity = pawn.AbsVelocity();
    float speed = std::hypot(velocity.x, velocity.y);
    if (speed < 1.0f)
    {
        return;
    }

    float scaled = std::min(speed * boost.factor, std::max(boost.maxSpeed, speed));
    velocity.x *= scaled / speed;
    velocity.y *= scaled / speed;
    pawn.SetAbsVelocity(velocity);
}

void BhopManager::ForceAutoHop(int slot)
{
    const VoltMod::Controller controller = _rt.Entities.Controller(slot);
    if (!(controller.Buttons() & IN_JUMP))
    {
        return;
    }

    Pawn pawn = controller.Pawn();
    if (!pawn.IsOnGround())
    {
        return;
    }

    Vector velocity = pawn.AbsVelocity();
    if (velocity.z > 0.0f)
    {
        return;  // The engine already applied the jump.
    }

    constexpr float DefaultJumpImpulse = 301.993378f;  // sqrt(2 * 800 * 57.0)
    velocity.z = _jumpImpulse ? _jumpImpulse.Get() : DefaultJumpImpulse;
    pawn.Launch(velocity);

    // Forced hops do not emit player_jump.
    OnPlayerJump(slot);
}

void BhopManager::OnPlayerSpawn(int slot)
{
    // Enabled mode already replicates values server-wide.
    if (_mode != Mode::Grants)
    {
        return;
    }

    Player* player = _rt.Players.Get(slot);
    bool granted = player && _granted.contains(player->SteamId());
    _grantedSlots[slot] = granted;

    // Restore the override after the engine's spawn snapshot.
    if (granted)
    {
        _conVars.ReplicateOverrides(slot);
    }
}

}  // namespace Bhop
