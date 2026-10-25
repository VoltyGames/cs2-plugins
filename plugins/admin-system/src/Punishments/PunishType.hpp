#pragma once

#include "Core/Permissions.hpp"

#include <VoltMod/Core/Text/EnumNames.hpp>
#include <array>
#include <cstddef>
#include <optional>
#include <string_view>

namespace AdminSystem::Punishments
{

/** The punishment kinds an admin can issue through the menu flow. */
enum class PunishType
{
    Kick,
    Ban,
    VoiceMute,
    TextMute,
    Warn,
};

/** How the server stores and treats each kind, so a new kind is one enumerator and one row. */
struct PunishTypeInfo
{
    PunishType Type;
    std::string_view AuditName;           ///< Stored in `admin_activity.action` and `punishments.kind`.
    std::string_view IssuedBroadcast;     ///< Translation key of the broadcast verb when issued.
    std::string_view LiftedBroadcast;     ///< Same when lifted; empty when the kind cannot be lifted.
    std::string_view RequiredPermission;  ///< The admin permission needed to issue it.
    bool Timed;                           ///< Carries a duration, and stays cached until it expires.
};

inline constexpr std::array<PunishTypeInfo, VoltMod::EnumCount<PunishType>> PunishTypes{{
    // Type, audit name, issued, lifted, permission, timed
    {PunishType::Kick, "kick", "broadcast.kicked", "", Permission::Kick, false},
    {PunishType::Ban, "ban", "broadcast.banned", "broadcast.unbanned", Permission::Ban, true},
    {PunishType::VoiceMute, "voice_mute", "broadcast.voiceMuted", "broadcast.voiceUnmuted", Permission::Mute, true},
    {PunishType::TextMute, "text_mute", "broadcast.textMuted", "broadcast.textUnmuted", Permission::Mute, true},
    {PunishType::Warn, "warn", "broadcast.warned", "", Permission::Mute, false},
}};

static_assert(
    [] {
        for (std::size_t i = 0; i < PunishTypes.size(); ++i)
        {
            if (VoltMod::EnumIndex(PunishTypes[i].Type) != i)
            {
                return false;
            }
        }
        return true;
    }(),
    "PunishTypes rows must follow the PunishType declaration order");

/** The row describing @p type. */
inline const PunishTypeInfo& LookUp(PunishType type)
{
    return PunishTypes[VoltMod::EnumIndex(type)];
}

/** Parse a punishment-type config string ("kick" | "ban" | "voiceMute" | "textMute" | "warn"),
 *  case-insensitively. */
inline std::optional<PunishType> ParsePunishType(std::string_view text)
{
    return VoltMod::Parse<PunishType>(text);
}

/** The kind stored under @p auditName; nullopt for a value this build does not know. */
inline std::optional<PunishType> ParseAuditAction(std::string_view auditName)
{
    for (const PunishTypeInfo& info : PunishTypes)
    {
        if (info.AuditName == auditName)
        {
            return info.Type;
        }
    }
    return std::nullopt;
}

/** Translation key of the human-facing action name (e.g. "action.ban"). */
inline std::string_view ActionTranslationKey(PunishType type)
{
    switch (type)
    {
    case PunishType::Kick:
        return "action.kick";
    case PunishType::Ban:
        return "action.ban";
    case PunishType::VoiceMute:
        return "action.voiceMute";
    case PunishType::TextMute:
        return "action.textMute";
    case PunishType::Warn:
        return "action.warn";
    }
    return "action.kick";
}

/** Translation key of the default reason for lifting this punishment; empty for a kind that cannot
 *  be lifted. */
inline std::string_view LiftReasonKey(PunishType type)
{
    switch (type)
    {
    case PunishType::Ban:
        return "reason.unbannedByAdmin";
    case PunishType::VoiceMute:
        return "reason.voiceUnmutedByAdmin";
    case PunishType::TextMute:
        return "reason.textUnmutedByAdmin";
    case PunishType::Kick:
    case PunishType::Warn:
        break;
    }
    return {};
}

}  // namespace AdminSystem::Punishments
