#pragma once

// clang-format off
// Generated from the plugin's migrations by `voltmod database header`. Do not edit.

#include <VoltMod/Database/Table.hpp>
#include <optional>

namespace AdminSystem::Database::Tables
{
  struct AdminGroups_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Name {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(name, name);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct Immunity {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(immunity, immunity);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Inherits {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(inherits, inherits);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct ChatPrefix {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(chat_prefix, chatPrefix);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct PrefixColor {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(prefix_color, prefixColor);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct NameColor {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(name_color, nameColor);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct MessageColor {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(message_color, messageColor);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct UpdatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(updated_at, updatedAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Permissions {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(permissions, permissions);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_groups, adminGroups);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               Name,
               Immunity,
               Inherits,
               ChatPrefix,
               PrefixColor,
               NameColor,
               MessageColor,
               CreatedAt,
               UpdatedAt,
               Permissions>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<AdminGroups_>, Name>>;
  };
  using AdminGroups = ::sqlpp::table_t<AdminGroups_>;

  struct Admins_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct SteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(steam_id, steamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct Name {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(name, name);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct DisplayPrefix {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(display_prefix, displayPrefix);
      using data_type = ::sqlpp::boolean;
      using has_default = std::true_type;
    };
    struct NameColor {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(name_color, nameColor);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct MessageColor {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(message_color, messageColor);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct UpdatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(updated_at, updatedAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct IsFrozen {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(is_frozen, isFrozen);
      using data_type = ::sqlpp::boolean;
      using has_default = std::true_type;
    };
    struct FrozenAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(frozen_at, frozenAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct FrozenBy {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(frozen_by, frozenBy);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct FreezeReason {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(freeze_reason, freezeReason);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct Permissions {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(permissions, permissions);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct GroupId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(group_id, groupId);
      using data_type = std::optional<::sqlpp::integral>;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admins, admins);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               SteamId,
               Name,
               DisplayPrefix,
               NameColor,
               MessageColor,
               CreatedAt,
               UpdatedAt,
               IsFrozen,
               FrozenAt,
               FrozenBy,
               FreezeReason,
               Permissions,
               GroupId>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<Admins_>, SteamId>,
               sqlpp::column_t<sqlpp::table_t<Admins_>, Name>>;
  };
  using Admins = ::sqlpp::table_t<Admins_>;

  struct Players_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct SteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(steam_id, steamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct Name {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(name, name);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct IpAddress {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(ip_address, ipAddress);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct FirstSeen {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(first_seen, firstSeen);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct LastSeen {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(last_seen, lastSeen);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct TotalConnections {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(total_connections, totalConnections);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct TotalPlaytime {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(total_playtime, totalPlaytime);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(players, players);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               SteamId,
               Name,
               IpAddress,
               FirstSeen,
               LastSeen,
               TotalConnections,
               TotalPlaytime>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<Players_>, SteamId>,
               sqlpp::column_t<sqlpp::table_t<Players_>, Name>>;
  };
  using Players = ::sqlpp::table_t<Players_>;

  struct Punishments_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Kind {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(kind, kind);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct TargetSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_steam_id, targetSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct TargetName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_name, targetName);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct TargetIp {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_ip, targetIp);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct AdminSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_steam_id, adminSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct AdminName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_name, adminName);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct Reason {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(reason, reason);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct ExpiresAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(expires_at, expiresAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Duration {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(duration, duration);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct IsActive {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(is_active, isActive);
      using data_type = ::sqlpp::boolean;
      using has_default = std::true_type;
    };
    struct RemovedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(removed_at, removedAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct RemovedBy {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(removed_by, removedBy);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct RemovedReason {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(removed_reason, removedReason);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(punishments, punishments);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               Kind,
               TargetSteamId,
               TargetName,
               TargetIp,
               AdminSteamId,
               AdminName,
               Reason,
               CreatedAt,
               ExpiresAt,
               Duration,
               IsActive,
               RemovedAt,
               RemovedBy,
               RemovedReason>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<Punishments_>, Kind>,
               sqlpp::column_t<sqlpp::table_t<Punishments_>, TargetSteamId>,
               sqlpp::column_t<sqlpp::table_t<Punishments_>, TargetName>,
               sqlpp::column_t<sqlpp::table_t<Punishments_>, AdminName>,
               sqlpp::column_t<sqlpp::table_t<Punishments_>, Reason>>;
  };
  using Punishments = ::sqlpp::table_t<Punishments_>;

  struct Servers_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Tag {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(tag, tag);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct Name {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(name, name);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct LastSeen {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(last_seen, lastSeen);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(servers, servers);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               Tag,
               Name,
               CreatedAt,
               LastSeen>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<Servers_>, Tag>>;
  };
  using Servers = ::sqlpp::table_t<Servers_>;

  struct AdminActivity_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct AdminSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_steam_id, adminSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct AdminName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_name, adminName);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct Action {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(action, action);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct TargetSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_steam_id, targetSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct TargetName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_name, targetName);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct Detail {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(detail, detail);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct ServerTag {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(server_tag, serverTag);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_activity, adminActivity);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               AdminSteamId,
               AdminName,
               Action,
               TargetSteamId,
               TargetName,
               Detail,
               ServerTag,
               CreatedAt>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<AdminActivity_>, AdminSteamId>,
               sqlpp::column_t<sqlpp::table_t<AdminActivity_>, Action>>;
  };
  using AdminActivity = ::sqlpp::table_t<AdminActivity_>;

  struct PlayerReports_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct ReporterSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(reporter_steam_id, reporterSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct ReporterName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(reporter_name, reporterName);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct ReporterIp {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(reporter_ip, reporterIp);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct TargetSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_steam_id, targetSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct TargetName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_name, targetName);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct TargetIp {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(target_ip, targetIp);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct ReasonCode {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(reason_code, reasonCode);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct Reason {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(reason, reason);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct ServerTag {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(server_tag, serverTag);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct MapName {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(map_name, mapName);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Status {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(status, status);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    struct HandledBy {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(handled_by, handledBy);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct HandledAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(handled_at, handledAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct Resolution {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(resolution, resolution);
      using data_type = ::sqlpp::text;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(player_reports, playerReports);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               ReporterSteamId,
               ReporterName,
               ReporterIp,
               TargetSteamId,
               TargetName,
               TargetIp,
               ReasonCode,
               Reason,
               ServerTag,
               MapName,
               CreatedAt,
               Status,
               HandledBy,
               HandledAt,
               Resolution>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<PlayerReports_>, ReporterSteamId>,
               sqlpp::column_t<sqlpp::table_t<PlayerReports_>, TargetSteamId>>;
  };
  using PlayerReports = ::sqlpp::table_t<PlayerReports_>;

  struct AdminServerGroups_ {
    struct Id {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(id, id);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    struct AdminSteamId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_steam_id, adminSteamId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct ServerTag {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(server_tag, serverTag);
      using data_type = ::sqlpp::text;
      using has_default = std::false_type;
    };
    struct GroupId {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(group_id, groupId);
      using data_type = ::sqlpp::integral;
      using has_default = std::false_type;
    };
    struct CreatedAt {
      SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(created_at, createdAt);
      using data_type = ::sqlpp::integral;
      using has_default = std::true_type;
    };
    SQLPP_CREATE_NAME_TAG_FOR_SQL_AND_CPP(admin_server_groups, adminServerGroups);
    template<typename T>
    using _table_columns = sqlpp::table_columns<T,
               Id,
               AdminSteamId,
               ServerTag,
               GroupId,
               CreatedAt>;
    using _required_insert_columns = sqlpp::detail::type_set<
               sqlpp::column_t<sqlpp::table_t<AdminServerGroups_>, AdminSteamId>,
               sqlpp::column_t<sqlpp::table_t<AdminServerGroups_>, ServerTag>,
               sqlpp::column_t<sqlpp::table_t<AdminServerGroups_>, GroupId>>;
  };
  using AdminServerGroups = ::sqlpp::table_t<AdminServerGroups_>;


}  // namespace AdminSystem::Database::Tables
