#include "Database/Repositories/Punishments.hpp"

#include "Database/Tables/Schema.hpp"

#include <VoltMod/Core/Time/Durations.hpp>
#include <string>
#include <utility>

namespace AdminSystem::Database
{

using Punishments::LookUp;
using Punishments::PunishType;
using VoltMod::Time;

// Names the COUNT column so the row reads as row.total.
SQLPP_CREATE_NAME_TAG(total);

/** Rows still in force at @p now: active, and permanent or not yet expired. */
static auto ActiveAt(const Tables::Punishments& t, int64_t now)
{
    return t.isActive == true and (t.expiresAt == 0 or t.expiresAt > now);
}

/** The one read behind both the blocking load and the async refresh. Warnings never expire and
 *  are counted in the database, so the minute refresh would only discard them. */
static auto ActiveQuery(int64_t now)
{
    return [now](auto& conn) {
        const Tables::Punishments t;
        std::vector<Punishment> records;
        for (const auto& row : conn(sqlpp::select(sqlpp::all_of(t))
                                        .from(t)
                                        .where(ActiveAt(t, now) and t.kind != LookUp(PunishType::Warn).AuditName)))
        {
            auto kind = Punishments::ParseAuditAction(row.kind);
            if (!kind)  // a kind written by a newer build; leave it to that build
            {
                continue;
            }

            records.push_back(Punishment{.Id = row.id,
                                         .Kind = *kind,
                                         .TargetSteamId = row.targetSteamId,
                                         .TargetName = std::string(row.targetName),
                                         .TargetIp = std::string(row.targetIp),
                                         .AdminSteamId = row.adminSteamId,
                                         .AdminName = std::string(row.adminName),
                                         .Reason = std::string(row.reason),
                                         .CreatedAt = row.createdAt,
                                         .ExpiresAt = row.expiresAt,
                                         .Duration = row.duration,
                                         .IsActive = row.isActive,
                                         .RemovedAt = row.removedAt,
                                         .RemovedBy = row.removedBy,
                                         .RemovedReason = std::string(row.removedReason)});
        }
        return records;
    };
}

std::vector<Punishment> PunishmentRepository::FindAllActive()
{
    return _db.RunOr("punishments_find_all_active", ActiveQuery(Time::Now()));
}

void PunishmentRepository::FindAllActiveAsync(std::function<void(std::vector<Punishment>)> onDone)
{
    _db.RunAsync("punishments_find_all_active", ActiveQuery(Time::Now()), std::move(onDone));
}

void PunishmentRepository::CreateAsync(const Punishment& record, std::function<void(int64_t)> onId)
{
    _db.RunAsync(
        "punishments_create",
        [record](auto& conn) {
            const Tables::Punishments t;
            return VoltMod::Insert(
                conn,
                sqlpp::insert_into(t).set(t.kind = LookUp(record.Kind).AuditName,
                                          t.targetSteamId = record.TargetSteamId, t.targetName = record.TargetName,
                                          t.targetIp = record.TargetIp, t.adminSteamId = record.AdminSteamId,
                                          t.adminName = record.AdminName, t.reason = record.Reason,
                                          t.createdAt = record.CreatedAt, t.expiresAt = record.ExpiresAt,
                                          t.duration = record.Duration, t.isActive = record.IsActive),
                "punishments");
        },
        std::move(onId));
}

void PunishmentRepository::RemoveAsync(int64_t recordId, int64_t removedBy, const std::string& reason)
{
    _db.RunAsync("punishments_remove", [recordId, removedBy, reason, now = Time::Now()](auto& conn) {
        const Tables::Punishments t;
        conn(sqlpp::update(t)
                 .set(t.isActive = false, t.removedAt = now, t.removedBy = removedBy, t.removedReason = reason)
                 .where(t.id == recordId));
    });
}

void PunishmentRepository::ExpireOldAsync()
{
    _db.RunAsync("punishments_expire_old", [now = Time::Now()](auto& conn) {
        const Tables::Punishments t;
        conn(sqlpp::update(t)
                 .set(t.isActive = false)
                 .where(t.isActive == true and t.expiresAt > 0 and t.expiresAt <= now));
    });
}

void PunishmentRepository::CountActiveAsync(PunishType kind, int64_t steamId, std::function<void(int)> onDone)
{
    _db.RunAsync(
        "punishments_count_active",
        [kind, steamId, now = Time::Now()](auto& conn) {
            const Tables::Punishments t;
            int active = 0;
            for (const auto& row :
                 conn(sqlpp::select(sqlpp::count(t.id).as(total))
                          .from(t)
                          .where(t.targetSteamId == steamId and t.kind == LookUp(kind).AuditName and ActiveAt(t, now))))
            {
                active = static_cast<int>(row.total);
            }
            return active;
        },
        std::move(onDone));
}

void PunishmentRepository::ClearAsync(PunishType kind, int64_t steamId)
{
    _db.RunAsync("punishments_clear", [kind, steamId](auto& conn) {
        const Tables::Punishments t;
        conn(sqlpp::update(t)
                 .set(t.isActive = false)
                 .where(t.targetSteamId == steamId and t.kind == LookUp(kind).AuditName and t.isActive == true));
    });
}

}  // namespace AdminSystem::Database
