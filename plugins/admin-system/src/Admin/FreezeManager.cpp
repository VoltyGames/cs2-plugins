#include "Admin/FreezeManager.hpp"

#include "Admin/AdminManager.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"
#include "Core/Permissions.hpp"
#include "Database/Repositories/Audit.hpp"

#include <VoltMod/Core/Log.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Messaging/Messages.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <format>

namespace AdminSystem::Admin
{

namespace Db = AdminSystem::Database;
namespace Log = VoltMod::Log;
namespace ChatColors = VoltMod::ChatColors;
using VoltMod::Time;

void FreezeManager::RefreshFromDatabase()
{
    // On a database error the callback never runs, so an outage never unfreezes anyone.
    _repos.Admins.FindFrozenAsync([this](std::vector<Db::FrozenAdmin> rows) {
        std::unordered_map<int64_t, Db::FrozenAdmin> fresh;
        for (auto& row : rows)
        {
            fresh.emplace(row.SteamId, std::move(row));
        }

        for (const auto& [steamId, row] : fresh)
        {
            if (!_frozen.contains(steamId))
            {
                NotifyFrozen(steamId);
            }
        }

        _frozen = std::move(fresh);
    });
}

std::optional<Db::FrozenAdmin> FreezeManager::GetFrozen(int64_t steamId) const
{
    auto it = _frozen.find(steamId);
    if (it == _frozen.end())
    {
        return std::nullopt;
    }
    return it->second;
}

void FreezeManager::Freeze(int64_t targetSteamId, const std::string& targetName, int64_t bySteamId,
                           const std::string& byName, const std::string& reason)
{
    ApplyFreeze(targetSteamId, targetName, bySteamId, byName, reason);

    Log::Warn("Admin {} ({}) frozen by {} ({}): {}", targetName, targetSteamId, byName, bySteamId, reason);
    _chat.BroadcastAction("broadcast.frozeAdmin", byName, targetName);
}

void FreezeManager::Unfreeze(int64_t targetSteamId, int64_t bySteamId, const std::string& byName)
{
    auto it = _frozen.find(targetSteamId);
    if (it == _frozen.end())
    {
        return;
    }

    _repos.Admins.ClearFrozenAsync(targetSteamId);

    std::string targetName = it->second.Name;
    _frozen.erase(it);

    RecordAudit(bySteamId, byName, "unfreeze_admin", targetSteamId, targetName, "");
    Log::Info("Admin {} ({}) unfrozen by {} ({}).", targetName, targetSteamId, byName, bySteamId);
    _chat.BroadcastAction("broadcast.unfrozeAdmin", byName, targetName);
}

void FreezeManager::RecordPunishment(int64_t adminSteamId, std::string_view adminName, std::string_view action,
                                     int64_t targetSteamId, std::string_view targetName, std::string_view detail)
{
    RecordAudit(adminSteamId, adminName, action, targetSteamId, targetName, detail);

    if (!_config.Get().abuseProtection.enabled)
    {
        return;
    }
    // The console, frozen admins and root admins never trip the rate check.
    const bool exempt =
        adminSteamId == 0 || IsFrozen(adminSteamId) || _admins.HasPermission(adminSteamId, Permission::Root);
    if (exempt)
    {
        return;
    }

    CheckAutoFreeze(adminSteamId, adminName);
}

void FreezeManager::RecordAudit(int64_t adminSteamId, std::string_view adminName, std::string_view action,
                                int64_t targetSteamId, std::string_view targetName, std::string_view detail)
{
    _repos.Activity.RecordAsync(adminSteamId, adminName, action, targetSteamId, targetName, detail,
                                _config.Get().server.tag);
}

void FreezeManager::ApplyFreeze(int64_t steamId, const std::string& name, int64_t bySteamId, const std::string& byName,
                                const std::string& reason)
{
    _repos.Admins.SetFrozenAsync(steamId, bySteamId, reason);

    _frozen[steamId] = {
        .SteamId = steamId, .Name = name, .FrozenAt = Time::Now(), .FrozenBy = bySteamId, .Reason = reason};

    RecordAudit(bySteamId, byName, "freeze_admin", steamId, name, reason);
    NotifyFrozen(steamId);
}

void FreezeManager::CheckAutoFreeze(int64_t adminSteamId, std::string_view adminName)
{
    const auto& cfg = _config.Get().abuseProtection;
    int64_t windowStart = Time::Now() - static_cast<int64_t>(cfg.windowMinutes) * 60;

    // FIFO on the worker: this count sees the audit insert that triggered the check.
    _repos.Activity.CountSinceAsync(
        // The name is copied: the completion runs on a later game frame, long after the caller's
        // view is gone.
        adminSteamId, windowStart, [this, adminSteamId, adminName = std::string(adminName)](Db::ActivityCounts counts) {
            const auto& limits = _config.Get().abuseProtection;
            bool tripped = (limits.maxBans > 0 && counts.Bans >= limits.maxBans) ||
                           (limits.maxKicks > 0 && counts.Kicks >= limits.maxKicks) ||
                           (limits.maxMutes > 0 && counts.Mutes >= limits.maxMutes) ||
                           (limits.maxWarnings > 0 && counts.Warnings >= limits.maxWarnings);
            if (!tripped || IsFrozen(adminSteamId))
            {
                return;
            }

            auto reason = std::format("Rate limit exceeded: {} bans, {} kicks, {} mutes, {} warnings in {} min",
                                      counts.Bans, counts.Kicks, counts.Mutes, counts.Warnings, limits.windowMinutes);
            ApplyFreeze(adminSteamId, adminName, 0, "", reason);
            Log::Warn("AUTO-FROZE admin {} ({}): {}", adminName, adminSteamId, reason);
            _chat.BroadcastAction("broadcast.autoFrozeAdmin", {}, {{"admin", adminName}});
        });
}

void FreezeManager::NotifyFrozen(int64_t steamId)
{
    auto* player = _rt.Players.BySteamId(steamId);
    if (!player)
    {
        return;
    }

    auto row = GetFrozen(steamId);
    int slot = player->Slot();
    auto notice = _rt.Translations.Get("freeze.notice", slot, {{"reason", row ? row->Reason : ""}});
    _rt.Messages.Send(slot, std::format("{}{}", ChatColors::Red, notice));
}

void FreezeManager::NotifyFrozenSoon(int slot, int64_t steamId)
{
    if (!VoltMod::IsValidSlot(slot))
    {
        return;
    }

    _pendingNotice[slot] = _rt.Scheduler.NextTick([this, steamId] { NotifyFrozen(steamId); });
}

}  // namespace AdminSystem::Admin
