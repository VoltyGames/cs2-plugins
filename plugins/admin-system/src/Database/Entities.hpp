#pragma once

#include "Punishments/PunishType.hpp"

#include <VoltMod/Core/Time/Durations.hpp>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace AdminSystem::Database
{

/** An administrator: the group and permissions they hold, plus their chat and panel preferences. */
struct Admin
{
    int64_t Id = 0;
    int64_t SteamId = 0;
    std::string Name;
    /** In memory this is the group on this server: an `admin_server_groups` row replaces
     *  `admins.group_id` at load time. */
    std::optional<int64_t> GroupId;
    std::vector<std::string> Permissions;

    /** Per-admin chat overrides. Empty color strings fall back to the admin's group. */
    bool DisplayPrefix = true;
    std::string NameColor;
    std::string MessageColor;

    int64_t CreatedAt = 0;
    int64_t UpdatedAt = 0;
};

/** A named set of permissions and immunity that admins inherit from. */
struct AdminGroup
{
    int64_t Id = 0;
    std::string Name;
    std::vector<std::string> Permissions;
    int32_t Immunity = 0;
    std::vector<std::string> Inherits;

    /** Optional chat styling, applied when an admin in this group speaks. Empty = no override. */
    std::string ChatPrefix;   /**< E.g., "[ADMIN]". Empty disables prefixing for this group. */
    std::string PrefixColor;  /**< Color name (see VoltMod::ChatColors::ParseNamed). */
    std::string NameColor;    /**< Color name for the speaker's display name. */
    std::string MessageColor; /**< Color name for the spoken message body. */

    int64_t CreatedAt = 0;
    int64_t UpdatedAt = 0;
};

/** One frozen admin, as returned by AdminRepository::FindFrozenAsync. */
struct FrozenAdmin
{
    int64_t SteamId = 0;
    std::string Name;
    int64_t FrozenAt = 0;
    int64_t FrozenBy = 0;  // 0 = automatic (rate-limit) freeze
    std::string Reason;
};

/** One punishment row. Bans carry TargetIp, warnings carry no duration, and a Kick is never
 *  stored; otherwise the kinds are identical, which is why they share a table. */
struct Punishment
{
    int64_t Id = 0;
    Punishments::PunishType Kind = Punishments::PunishType::Ban;
    int64_t TargetSteamId = 0;
    std::string TargetName;
    std::string TargetIp;
    int64_t AdminSteamId = 0;
    std::string AdminName;
    std::string Reason;
    int64_t CreatedAt = 0;
    int64_t ExpiresAt = 0;
    int64_t Duration = 0;
    bool IsActive = true;
    int64_t RemovedAt = 0;
    int64_t RemovedBy = 0;
    std::string RemovedReason;

    bool IsPermanent() const { return ExpiresAt == 0; }
    bool IsExpired() const { return !IsPermanent() && VoltMod::Time::IsExpired(ExpiresAt); }
};

/** A player-submitted report. Only the columns the game server writes; the website-owned triage
 *  columns (status/handled_by/handled_at/resolution) keep their database defaults. */
struct Report
{
    int64_t Id = 0;
    int64_t ReporterSteamId = 0;
    std::string ReporterName;
    std::string ReporterIp;
    int64_t TargetSteamId = 0;
    std::string TargetName;
    std::string TargetIp;
    std::string ReasonCode;
    std::string Reason;
    std::string ServerTag;
    std::string MapName;
    int64_t CreatedAt = 0;
};

/** Counts of rate-limited action types inside an abuse-detection window. */
struct ActivityCounts
{
    int Bans = 0;
    int Kicks = 0;
    int Mutes = 0;  // voice + text combined
    int Warnings = 0;
};

}  // namespace AdminSystem::Database
