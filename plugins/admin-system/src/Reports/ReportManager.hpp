#pragma once

#include "Config/ConfigManager.hpp"
#include "Database/Repositories.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Time/Cooldown.hpp>
#include <VoltMod/Players/Player.hpp>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>

namespace AdminSystem::Reports
{

/** Why a report attempt was refused. */
enum class ReportDenial
{
    Allowed,
    Disabled,
    OnCooldown,
};

/** Gate verdict; SecondsLeft carries the remaining wait for @ref ReportDenial::OnCooldown. */
struct ReportGate
{
    ReportDenial Reason = ReportDenial::Allowed;
    int64_t SecondsLeft = 0;

    explicit operator bool() const { return Reason == ReportDenial::Allowed; }
};

/**
 * Owns player-submitted reports: the anti-spam gate and the single database write. Nothing in-game
 * reads them back; an upstream website triages the `player_reports` table.
 *
 * Both throttles are keyed by SteamID, not slot, and survive disconnect and map change -
 * otherwise rejoining would clear a cooldown.
 */
class ReportManager
{
public:
    ReportManager(Database::Repositories& repos, const Config::ConfigManager& config, VoltMod::Runtime& runtime)
        : _repos(repos), _config(config), _rt(runtime)
    {}

    /** Enabled/cooldown gate - the `!report` entry check, before a target is chosen. */
    ReportGate CanReport(int64_t reporterSteamId) const;

    /** The above plus "already reported this target inside the duplicate window". */
    bool CanReport(int64_t reporterSteamId, int64_t targetSteamId) const;

    /**
     * Re-check the gate, persist, and start the reporter's cooldown. @p onDone reports the write
     * outcome on the game thread; false also covers a refused gate. A failed write releases the
     * cooldown, so an outage costs the reporter nothing.
     */
    void Submit(const VoltMod::Player& reporter, const VoltMod::Player& target, const std::string& reasonCode,
                const std::string& reasonText, std::function<void(bool ok)> onDone);

private:
    Database::Repositories& _repos;
    const Config::ConfigManager& _config;
    VoltMod::Runtime& _rt;

    /** Both CanReport overloads, parameterized by @p now so a submit gates and stamps from one
     *  clock read. @p targetSteamId engages the per-target duplicate window. */
    ReportGate EvaluateGate(int64_t reporterSteamId, std::optional<int64_t> targetSteamId, int64_t now) const;

    /** Claim the reporter's next slot before the write (so a double-press can't produce two rows)
     *  and sweep both throttles, this being their only growth point. */
    void StartCooldown(int64_t reporterSteamId, int64_t targetSteamId, int64_t now);
    void ReleaseCooldown(int64_t reporterSteamId, int64_t targetSteamId);

    /** Intervals come from reloadable config, so they are passed per call rather than constructed. */
    VoltMod::Cooldown<int64_t> _anyTarget;               // reporter -> last report of anyone
    VoltMod::PairCooldown<int64_t, int64_t> _perTarget;  // (reporter, target) -> last report of that player
};

}  // namespace AdminSystem::Reports
