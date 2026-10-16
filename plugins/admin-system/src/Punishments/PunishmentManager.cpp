#include "Punishments/PunishmentManager.hpp"

#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Log.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Engine/Interfaces.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <algorithm>
#include <engine2/ivengineserver2.h>
#include <utility>

using AdminSystem::Database::Punishment;
using VoltMod::Time;

namespace AdminSystem::Punishments
{

namespace Log = VoltMod::Log;

/** Fill in the times an admin did not give. */
static void StampTimes(Punishment& record)
{
    if (record.CreatedAt == 0)
    {
        record.CreatedAt = Time::Now();
    }
    if (record.Duration > 0 && record.ExpiresAt == 0)
    {
        record.ExpiresAt = Time::GetExpirationTime(record.Duration);
    }
}

// Make the engine re-evaluate channels negotiated before the (un)mute landed. The
// SetClientListening hook still enforces the cached decision.
static void RefreshVoiceChannel(VoltMod::Runtime& rt, int64_t senderSteamId, bool muted)
{
    auto* engine = rt.Unsafe.Interfaces.Engine;
    if (!engine)
    {
        return;
    }

    auto* sender = rt.Players.BySteamId(senderSteamId);
    if (!sender)
    {
        return;
    }

    int senderSlot = sender->Slot();
    for (int i = 0; i < 64; ++i)
    {
        if (i == senderSlot)
        {
            continue;
        }
        if (!rt.Players.Get(i))
        {
            continue;
        }
        engine->SetClientListening(CPlayerSlot(i), CPlayerSlot(senderSlot), !muted);
    }
}

bool PunishmentManager::LoadActivePunishments()
{
    SwapCaches(_repos.Punishments.FindAllActive());
    Log::Info("Loaded active punishments: {} ban(s), {} voice mute(s), {} text mute(s).",
              CacheFor(PunishType::Ban).size(), CacheFor(PunishType::VoiceMute).size(),
              CacheFor(PunishType::TextMute).size());
    return true;
}

PunishmentManager::ActivePage PunishmentManager::GetActive(std::span<const PunishType> kinds, std::size_t limit) const
{
    // Point at the cached rows rather than copying them: a busy server holds thousands of active
    // punishments and the caller keeps only `limit`.
    std::vector<const Punishment*> matches;
    for (PunishType kind : kinds)
    {
        const Cache& cache = CacheFor(kind);
        matches.reserve(matches.size() + cache.size());
        for (const auto& [steamId, record] : cache)
        {
            if (!record.IsExpired())
            {
                matches.push_back(&record);
            }
        }
    }

    ActivePage page{.Total = matches.size()};
    const std::size_t shown = std::min(limit, matches.size());

    std::partial_sort(matches.begin(), matches.begin() + static_cast<std::ptrdiff_t>(shown), matches.end(),
                      [](const Punishment* a, const Punishment* b) { return a->CreatedAt > b->CreatedAt; });

    page.Rows.reserve(shown);
    for (std::size_t i = 0; i < shown; ++i)
    {
        page.Rows.push_back(*matches[i]);
    }
    return page;
}

std::optional<Punishment> PunishmentManager::GetActive(PunishType kind, int64_t steamId)
{
    Cache& cache = CacheFor(kind);
    auto it = cache.find(steamId);
    if (it == cache.end())
    {
        return std::nullopt;
    }
    if (it->second.IsExpired())
    {
        cache.erase(it);
        if (kind == PunishType::VoiceMute)
        {
            RefreshVoiceChannel(_rt, steamId, false);
        }
        return std::nullopt;
    }
    return it->second;
}

bool PunishmentManager::IsPunished(PunishType kind, int64_t steamId) const
{
    return CacheFor(kind).contains(steamId);
}

void PunishmentManager::Issue(Punishment& record)
{
    if (record.Kind == PunishType::Kick)
    {
        return;  // a kick stores no row; IssuePunishment applies and broadcasts it directly
    }

    StampTimes(record);

    if (IsCached(record.Kind))
    {
        // Cache first so the punishment bites this frame; the id lands later, and only if
        // nothing has replaced the entry.
        Cache& cache = CacheFor(record.Kind);
        cache[record.TargetSteamId] = record;
        _repos.Punishments.CreateAsync(record, [&cache, steamId = record.TargetSteamId](int64_t id) {
            if (auto it = cache.find(steamId); it != cache.end() && it->second.Id == 0)
            {
                it->second.Id = id;
            }
        });
    }
    else
    {
        _repos.Punishments.CreateAsync(record);
    }

    if (record.Kind == PunishType::Ban)
    {
        if (auto* player = _rt.Players.BySteamId(record.TargetSteamId))
        {
            KickDeferred(player->Slot(), record.TargetSteamId, record.Reason);
        }
    }
    else if (record.Kind == PunishType::VoiceMute)
    {
        RefreshVoiceChannel(_rt, record.TargetSteamId, true);
    }

    const PunishTypeInfo& info = InfoFor(record.Kind);
    _chat.BroadcastPunishment(info.IssuedBroadcast, record.AdminName, record.TargetName, record.Reason,
                              info.Timed ? std::optional{record.Duration} : std::nullopt);

    if (record.Kind == PunishType::Warn)
    {
        EscalateWarning(record);
    }
}

void PunishmentManager::EscalateWarning(const Punishment& warning)
{
    // Built now so the callback carries only what the ban needs; its reason is read when it fires.
    Punishment autoBan{.Kind = PunishType::Ban,
                       .TargetSteamId = warning.TargetSteamId,
                       .TargetName = warning.TargetName,
                       .AdminSteamId = warning.AdminSteamId,
                       .AdminName = warning.AdminName,
                       .Duration = 0};  // permanent escalation

    // FIFO: this count sees the insert Issue just enqueued, and lands on the game thread.
    _repos.Punishments.CountActiveAsync(
        PunishType::Warn, warning.TargetSteamId, [this, autoBan = std::move(autoBan)](int active) mutable {
            const int threshold = _config.Get().punishments.warningThreshold;
            if (threshold <= 0 || active < threshold)
            {
                return;
            }

            Log::Info("Warning threshold ({}) reached for {} -- escalating to ban.", threshold, autoBan.TargetSteamId);
            _repos.Punishments.ClearAsync(PunishType::Warn, autoBan.TargetSteamId);

            autoBan.Reason = _config.Get().punishments.defaultBanReason;
            Issue(autoBan);
        });
}

bool PunishmentManager::Remove(PunishType kind, int64_t recordId, int64_t removedBy, const std::string& reason)
{
    Cache& cache = CacheFor(kind);
    auto it = std::ranges::find_if(cache, [recordId](const auto& entry) { return entry.second.Id == recordId; });
    if (it == cache.end())
    {
        return false;  // already lifted, possibly by another server - nothing to remove
    }

    RemoveCached(kind, it, removedBy, reason);
    return true;
}

bool PunishmentManager::RemoveBySteamId(PunishType kind, int64_t steamId, int64_t removedBy, const std::string& reason)
{
    // The caches mirror every active row, so a miss needs no database lookup.
    Cache& cache = CacheFor(kind);
    auto it = cache.find(steamId);
    if (it == cache.end())
    {
        return false;
    }

    RemoveCached(kind, it, removedBy, reason);
    return true;
}

std::string PunishmentManager::AdminDisplayName(int64_t steamId) const
{
    if (const VoltMod::Player* admin = _rt.Players.BySteamId(steamId))
    {
        return admin->Name();
    }
    return _rt.Translations.Get("common.console");
}

void PunishmentManager::RemoveCached(PunishType kind, Cache::iterator it, int64_t removedBy, const std::string& reason)
{
    const int64_t steamId = it->first;
    _repos.Punishments.RemoveAsync(it->second.Id, removedBy, reason);
    _chat.BroadcastPunishment(InfoFor(kind).LiftedBroadcast, AdminDisplayName(removedBy), it->second.TargetName, reason,
                              std::nullopt);

    // Erased before the refresh, which re-reads the cache through the listening hook.
    CacheFor(kind).erase(it);
    if (kind == PunishType::VoiceMute)
    {
        RefreshVoiceChannel(_rt, steamId, false);
    }
}

void PunishmentManager::KickDeferred(int slot, int64_t steamId, std::string reason)
{
    if (!VoltMod::IsValidSlot(slot))
    {
        return;
    }

    _pendingKick[slot] = _rt.Scheduler.NextTick([&rt = _rt, slot, steamId, reason = std::move(reason)] {
        // The seat can change hands before this fires; kicking whoever took it is not the ban.
        if (rt.Players.Get(VoltMod::PlayerRef{slot, steamId}))
        {
            rt.Entities.Controller(slot).Kick(reason);
        }
    });
}

void PunishmentManager::ExpireOldPunishments()
{
    _repos.Punishments.ExpireOldAsync();
    // FIFO: this snapshot runs after the expirations above have landed.
    RefreshCachesAsync();
}

void PunishmentManager::RefreshCachesAsync()
{
    _repos.Punishments.FindAllActiveAsync([this](std::vector<Punishment> rows) { SwapCaches(std::move(rows)); });
}

void PunishmentManager::SwapCaches(std::vector<Punishment> rows)
{
    // Taken before the swap: voice mutes that expired this sweep still need a channel refresh.
    const Cache previouslyVoiceMuted = std::exchange(CacheFor(PunishType::VoiceMute), {});

    for (Cache& cache : _active)
    {
        cache.clear();
    }
    for (auto& row : rows)
    {
        if (IsCached(row.Kind))
        {
            CacheFor(row.Kind)[row.TargetSteamId] = std::move(row);
        }
    }

    const Cache& voiceMuted = CacheFor(PunishType::VoiceMute);
    for (const auto& [steamId, record] : previouslyVoiceMuted)
    {
        if (!voiceMuted.contains(steamId))
        {
            RefreshVoiceChannel(_rt, steamId, false);
        }
    }
}

}  // namespace AdminSystem::Punishments
