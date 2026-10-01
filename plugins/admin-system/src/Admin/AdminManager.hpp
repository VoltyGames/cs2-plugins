#pragma once

#include "Config/ConfigManager.hpp"
#include "Database/Entities.hpp"
#include "Database/Repositories.hpp"

#include <VoltMod/Messaging/ChatColors.hpp>
#include <functional>
#include <set>
#include <string>
#include <string_view>
#include <unordered_map>

namespace AdminSystem::Admin
{

/**
 * Resolved chat styling for a single admin, from their group's ChatPrefix (with config-driven
 * fallback when the group has none).
 */
struct AdminChatStyle
{
    std::string Prefix;        /**< E.g., "[ADMIN]". Empty for non-admins. */
    std::string PrefixColor;   /**< Color name; resolved via ChatColors::ParseNamed. */
    std::string NameColor;     /**< Color name for the speaker's display name. */
    std::string MessageColor;  /**< Color name for the message body. */
    bool DisplayPrefix = true; /**< Per-admin toggle; suppresses the prefix when false. */

    bool HasPrefix() const { return DisplayPrefix && !Prefix.empty(); }
};

/**
 * Owns admin records: permission resolution, immunity, and chat styling. Each admin's own and
 * group permissions are merged into one set at load, so a check is a lookup.
 *
 * The permission answers here are the admin's *granted* permissions and nothing else. Abuse-protection
 * freezes are layered on top by @ref Access, which is what command, menu and action code asks -
 * keeping the freeze gate out of here is what breaks the AdminManager/FreezeManager cycle.
 */
class AdminManager
{
public:
    AdminManager(Database::Repositories& repos, const Config::ConfigManager& config) : _repos(repos), _config(config) {}

    bool LoadAdmins();
    bool LoadGroups();
    bool Reload();
    bool IsAdmin(int64_t steamId);
    const Database::Admin* GetAdmin(int64_t steamId);
    /** True if the admin holds @p permission, "*", or a wildcard over any of its prefixes ("admin.*"). */
    bool HasPermission(int64_t steamId, std::string_view permission);
    int GetImmunity(int64_t steamId);
    /** Strictly higher immunity. Punishments are the only rank-gated verbs. */
    bool CanPunish(int64_t adminSteamId, int64_t targetSteamId);

    void AddAdmin(const Database::Admin& admin);
    void AddGroup(const Database::AdminGroup& group);
    void RemoveAdmin(int64_t steamId);
    size_t AdminCount() const { return _admins.size(); }
    size_t GroupCount() const { return _groups.size(); }

    /**
     * Resolve the chat styling that should decorate this admin's chat lines. Returns an
     * empty `AdminChatStyle` (HasPrefix() == false) for non-admins.
     */
    AdminChatStyle GetChatStyle(int64_t steamId);

    /** Persist + apply per-admin chat-style overrides. Empty color strings revert that slot
     *  back to the admin's group default. Unknown admins are ignored. */
    void UpdateChatStyleAsync(int64_t steamId, bool displayPrefix, const std::string& nameColor,
                              const std::string& messageColor);

private:
    using PermissionSet = std::set<std::string, std::less<>>;

    Database::Repositories& _repos;
    const Config::ConfigManager& _config;

    const Database::AdminGroup* FindGroup(const Database::Admin& admin) const;
    PermissionSet ResolvePermissions(const Database::Admin& admin);

    std::unordered_map<int64_t, Database::Admin> _admins;
    std::unordered_map<int64_t, Database::AdminGroup> _groups;

    std::unordered_map<int64_t, PermissionSet> _resolvedPermissions;

    /** Cached resolved chat styles per admin steam ID; invalidated on Reload(). */
    std::unordered_map<int64_t, AdminChatStyle> _resolvedStyles;
};

}  // namespace AdminSystem::Admin
