#pragma once

#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"
#include "Database/Repositories.hpp"
#include "Punishments/PunishType.hpp"

#include <VoltMod/Runtime.hpp>
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

namespace AdminSystem::Punishments
{

/** Active bans, mutes and warnings. The cache is updated synchronously so a punishment bites the
 *  frame it is issued; the database write is async and backfills the row id when it returns. */
class PunishmentManager
{
public:
    PunishmentManager(Database::Repositories& repos, const Config::ConfigManager& config, VoltMod::Runtime& runtime,
                      Core::ChatService& chat)
        : _repos(repos), _config(config), _rt(runtime), _chat(chat)
    {}

    bool LoadActivePunishments();

    /** What @ref GetActive found: the rows to draw, and how many matched before the cap. */
    struct ActivePage
    {
        std::vector<Database::Punishment> Rows;
        std::size_t Total = 0;
    };

    /** The most recent active rows across @p kinds, newest first and at most @p limit of them.
     *  Drives the lift menu, which cannot usefully hold the thousands a busy server collects. */
    ActivePage GetActive(std::span<const PunishType> kinds, std::size_t limit) const;

    /** The active row of @p kind against @p steamId, dropping it when it has since expired. */
    std::optional<Database::Punishment> GetActive(PunishType kind, int64_t steamId);

    /** Whether @p steamId is currently punished with @p kind. The tick-rate check: it does not
     *  sweep expiries, which the minute timer does. */
    bool IsPunished(PunishType kind, int64_t steamId) const;

    /** Persist and apply @p record: cache, broadcast, kick a banned player, escalate a warning
     *  past the threshold. A Kick stores no row and is ignored; the write is async and logs its
     *  own failure. */
    void Issue(Database::Punishment& record);

    /** Lift by row id. False when it was already gone, possibly lifted on another server. */
    bool Remove(PunishType kind, int64_t recordId, int64_t removedBy, const std::string& reason);

    /** Lift whatever of @p kind is active against @p steamId. False when nothing was. */
    bool RemoveBySteamId(PunishType kind, int64_t steamId, int64_t removedBy, const std::string& reason);

    /** Mark expired rows inactive in the DB and rebuild the caches (all async). */
    void ExpireOldPunishments();

    /** Kick @p slot next frame, and only if @p steamId still occupies it. Deferred because
     *  callers run inside target hooks, where disconnecting interrupts the virtual call. */
    void KickDeferred(int slot, int64_t steamId, std::string reason);

    /** The admin's name; an offline admin falls back to a console label. */
    std::string AdminDisplayName(int64_t steamId) const;

private:
    using Cache = std::unordered_map<int64_t, Database::Punishment>;  ///< keyed by TargetSteamId

    /** Whether @p kind is cached: the timed kinds. A cache holds one row per player, which a warning
     *  breaks and a kick has none of, so those two are counted in the database instead. */
    static bool IsCached(PunishType kind) { return LookUp(kind).Timed; }

    Cache& GetCache(PunishType kind) { return _active[VoltMod::EnumIndex(kind)]; }
    const Cache& GetCache(PunishType kind) const { return _active[VoltMod::EnumIndex(kind)]; }

    /** Lift the cached entry @p it points at: persist, drop it, refresh voice, broadcast. */
    void RemoveCached(PunishType kind, Cache::iterator it, int64_t removedBy, const std::string& reason);

    /** Re-query every active row off-thread and swap the caches when they arrive. */
    void RefreshCachesAsync();
    void SwapCaches(std::vector<Database::Punishment> rows);
    /** Auto-ban once a player has collected the configured number of active warnings. */
    void EscalateWarning(const Database::Punishment& warning);

    Database::Repositories& _repos;
    const Config::ConfigManager& _config;
    VoltMod::Runtime& _rt;
    Core::ChatService& _chat;
    VoltMod::PerSlot<VoltMod::Subscription> _pendingKick;

    /** Indexed by PunishType; the slots @ref IsCached rejects stay empty. */
    std::array<Cache, VoltMod::EnumCount<PunishType>> _active;
};

}  // namespace AdminSystem::Punishments
