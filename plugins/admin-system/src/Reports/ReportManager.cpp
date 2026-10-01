#include "Reports/ReportManager.hpp"

#include "Config/ConfigManager.hpp"
#include "Database/Repositories/Reports.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Log.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Runtime.hpp>
#include <algorithm>
#include <utility>

using VoltMod::Time;

namespace AdminSystem::Reports
{

namespace Log = VoltMod::Log;

ReportGate ReportManager::EvaluateGate(int64_t reporterSteamId, std::optional<int64_t> targetSteamId, int64_t now) const
{
    const auto& config = _config.Get().reports;
    if (!config.enabled)
    {
        return {ReportDenial::Disabled};
    }

    if (int64_t wait = _anyTarget.SecondsLeft(reporterSteamId, now, config.cooldownSec); wait > 0)
    {
        return {ReportDenial::OnCooldown, wait};
    }

    if (targetSteamId)
    {
        const auto pair = std::pair{reporterSteamId, *targetSteamId};
        if (int64_t wait = _perTarget.SecondsLeft(pair, now, config.duplicateWindowSec); wait > 0)
        {
            return {ReportDenial::OnCooldown, wait};
        }
    }

    return {};
}

ReportGate ReportManager::CanReport(int64_t reporterSteamId) const
{
    return EvaluateGate(reporterSteamId, std::nullopt, Time::Now());
}

bool ReportManager::CanReport(int64_t reporterSteamId, int64_t targetSteamId) const
{
    return static_cast<bool>(EvaluateGate(reporterSteamId, targetSteamId, Time::Now()));
}

void ReportManager::Submit(const VoltMod::Player& reporter, const VoltMod::Player& target,
                           const std::string& reasonCode, const std::string& reasonText,
                           std::function<void(bool)> onDone)
{
    const int64_t reporterSteamId = reporter.SteamId();
    const int64_t targetSteamId = target.SteamId();
    const int64_t now = Time::Now();

    if (!EvaluateGate(reporterSteamId, targetSteamId, now))
    {
        if (onDone)
        {
            onDone(false);
        }
        return;
    }

    Database::Report report{
        .ReporterSteamId = reporterSteamId,
        .ReporterName = reporter.Name(),
        .ReporterIp = std::string(reporter.Ip()),
        .TargetSteamId = targetSteamId,
        .TargetName = target.Name(),
        .TargetIp = std::string(target.Ip()),
        .ReasonCode = reasonCode,
        .Reason = reasonText,
        .ServerTag = _config.Get().server.tag,
        .MapName = _rt.Map.Current(),
        .CreatedAt = now,
    };

    StartCooldown(reporterSteamId, targetSteamId, now);
    Log::Info("Report: {} ({}) reported {} ({}) for '{}' [{}]", report.ReporterName, reporterSteamId, report.TargetName,
              targetSteamId, reasonText, reasonCode);

    _repos.Reports.CreateAsync(report, [this, reporterSteamId, targetSteamId, onDone = std::move(onDone)](bool ok) {
        // The write is the only database-health signal there is, so a failure refunds the
        // attempt rather than costing the reporter a cooldown.
        if (!ok)
        {
            ReleaseCooldown(reporterSteamId, targetSteamId);
        }
        if (onDone)
        {
            onDone(ok);
        }
    });
}

void ReportManager::StartCooldown(int64_t reporterSteamId, int64_t targetSteamId, int64_t now)
{
    _anyTarget.Start(reporterSteamId, now);
    _perTarget.Start({reporterSteamId, targetSteamId}, now);

    // Both maps only grow here, so this is the one place worth sweeping.
    const auto& config = _config.Get().reports;
    const int64_t horizon = std::max(config.cooldownSec, config.duplicateWindowSec);
    _anyTarget.RemoveExpired(now, horizon);
    _perTarget.RemoveExpired(now, horizon);
}

void ReportManager::ReleaseCooldown(int64_t reporterSteamId, int64_t targetSteamId)
{
    _anyTarget.Reset(reporterSteamId);
    _perTarget.Reset({reporterSteamId, targetSteamId});
}

}  // namespace AdminSystem::Reports
