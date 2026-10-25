#pragma once

#include "Config.hpp"
#include "MovementConVars.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Signals/Subscriptions.hpp>
#include <array>
#include <chrono>
#include <cstdint>
#include <optional>
#include <unordered_set>

namespace Bhop
{

/**
 * Bhop policy: server-wide mode, per-player session grants, and the hop-chain boost. The convar
 * mechanics both modes rely on live in MovementConVars; this class decides when to drive them.
 *
 * "enabled" mode sets the configured movement convars through the engine path, so they replicate
 * to every client and the whole feature is client-predicted (ping-free). "grants" mode leaves the
 * server untouched and enables bhop per player: the client gets the convar values via
 * ConVar::SendTo (its prediction auto-jumps) while the server flips the same convars only
 * around that player's RunCommand via the framework's Movement hook.
 */
class BhopManager
{
public:
    /** Registers the listeners, which check the mode when they fire, and the console commands. */
    BhopManager(VoltMod::Runtime& runtime, ConfigManager& config);

    /** Apply the configured mode. Called from Load, once the settings are known good, because it
     *  changes server convars. */
    void ApplySettings();

    /** Session grant/revoke for @p steamId; applies immediately when the player is online. */
    void Grant(int64_t steamId, bool enabled);
    bool IsGranted(int64_t steamId) const { return _granted.contains(steamId); }

    /** Re-read settings.jsonc and re-apply (bhop_reload): restores prior convar values first. */
    void ReloadSettings();

    void OnPlayerDisconnect(VoltMod::Player& player);

private:
    enum class Mode : uint8_t
    {
        Enabled,
        Grants,
    };

    void RegisterConsoleCommands();  // ConsoleCommands.cpp

    void OnRunCommandPre(int slot);
    void OnRunCommandPost(int slot);
    void OnPlayerJump(int slot);
    void OnPlayerSpawn(int slot);
    void ForceAutoHop(int slot);

    bool IsActiveSlot(int slot) const;

    VoltMod::Runtime& _rt;
    ConfigManager& _config;
    Mode _mode = Mode::Enabled;
    MovementConVars _conVars;
    /** Read every frame per granted player by ForceAutoHop; empty when the server has no such
     *  convar, in which case the engine default stands in. */
    VoltMod::ConVar<float> _jumpImpulse;

    std::unordered_set<int64_t> _granted;
    // Per-slot mirror of _granted for the movement hot path, where a steamId lookup per tick
    // would be wasteful. Kept in lockstep with _granted by Grant/OnPlayerSpawn/OnPlayerDisconnect.
    std::array<bool, VoltMod::MaxPlayers> _grantedSlots{};
    std::array<std::chrono::steady_clock::time_point, VoltMod::MaxPlayers> _lastJump{};

    /** Listener registrations, released together. Declared last: reverse member destruction
     *  stops the callbacks before the state they capture goes away. */
    VoltMod::Subscriptions _subs;

    /** The Movement pair, held apart from @ref _subs because only grants mode needs it and the
     *  hook arms on its first subscription: dropping these disarms the per-usercmd vtable hook
     *  for a server that never leaves the default mode. Rebuilt by ApplySettings. */
    VoltMod::Subscriptions _movementSubs;
};

}  // namespace Bhop
