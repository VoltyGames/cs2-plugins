#include "Core/ChatService.hpp"

#include "Config/ConfigManager.hpp"

#include <VoltMod/Core/Text/Strings.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Messaging/Messages.hpp>
#include <VoltMod/Runtime.hpp>
#include <format>
#include <optional>

using VoltMod::Strings;
using VoltMod::Time;

namespace AdminSystem::Core
{

namespace ChatColors = VoltMod::ChatColors;

/** Layout for "{prefix} {actor} {phrase}" action lines. */
struct AdminLineStyle
{
    std::string Prefix;
    std::string_view PrefixColor;
    std::string_view NameColor;
    std::string_view PhraseColor;
};

/** "{prefix} {actor} {phrase}", e.g. "[ADMIN] Bob went stealth". An empty actor is left out. */
static std::string FormatAdminLine(const AdminLineStyle& style, std::string_view actorName, std::string_view phrase)
{
    if (actorName.empty())
    {
        return std::format("{}{} {}{}", style.PrefixColor, style.Prefix, style.PhraseColor, phrase);
    }

    return std::format("{}{} {}{}{} {}{}", style.PrefixColor, style.Prefix, style.NameColor, actorName,
                       ChatColors::Default, style.PhraseColor, phrase);
}

/** Single-target variant: "{prefix} {actor} {phrase} {target}", e.g. "[ADMIN] Bob slapped Alice". */
static std::string FormatAdminLine(const AdminLineStyle& style, std::string_view actorName, std::string_view phrase,
                                   std::string_view targetName)
{
    return std::format("{}{} {}", FormatAdminLine(style, actorName, phrase), style.NameColor, targetName);
}

/** Token variant for multi-target phrases, e.g. "swapped {a} and {b}": each mapped name is
 *  substituted into `phraseTemplate` wrapped in the name color. */
static std::string FormatAdminLine(const AdminLineStyle& style, std::string_view actorName,
                                   std::string_view phraseTemplate,
                                   const std::map<std::string, std::string>& nameTokens)
{
    // Names sit inside the colored phrase, so wrap each in the name color before substituting.
    std::map<std::string, std::string> colored;
    for (const auto& [token, name] : nameTokens)
    {
        colored.emplace(token, std::format("{}{}{}", style.NameColor, name, style.PhraseColor));
    }

    return FormatAdminLine(style, actorName, Strings::SubstituteTokens(std::string(phraseTemplate), colored));
}

void ChatService::Reply(int slot, std::string_view message)
{
    _rt.Messages.Send(slot, message);
}

void ChatService::ReplyLink(int slot, std::string_view label, std::string_view url)
{
    _rt.Messages.Send(slot, label);
    _rt.Messages.Send(slot, std::format("{}{}", ChatColors::Olive, url));
}

void ChatService::NoPermission(int slot)
{
    auto msg = std::format("{}{}", ChatColors::Red, _rt.Translations.Get("cmd.noPermission", slot));
    _rt.Messages.Send(slot, msg);
}

/** The colouring every broadcast shares, so no two lines disagree on the tag. */
static AdminLineStyle BuildStyle(const Config::ChatSettings& cfg)
{
    return {.Prefix = cfg.fallbackPrefix,
            .PrefixColor = ChatColors::ParseNamed(cfg.fallbackPrefixColor),
            .NameColor = ChatColors::ParseNamed(cfg.fallbackNameColor),
            .PhraseColor = ChatColors::ParseNamed(cfg.fallbackMessageColor)};
}

void ChatService::BroadcastPunishment(std::string_view actionKey, std::string_view adminName,
                                      std::string_view targetName, std::string_view reason,
                                      std::optional<int64_t> durationSec)
{
    if (!_config.Get().chat.broadcastPunishments)
    {
        return;
    }

    const AdminLineStyle style = BuildStyle(_config.Get().chat);

    std::string durationSuffix;
    if (durationSec)
    {
        std::string duration =
            *durationSec > 0 ? Time::FormatDuration(*durationSec) : _rt.Translations.Get("broadcast.permanent");
        durationSuffix = std::format(" ({})", duration);
    }

    // The verb is what names the punishment, so it keeps its own colour.
    const std::string phrase = std::format("{}{}{}", ChatColors::Red, BroadcastPhrase(actionKey), style.PhraseColor);
    const std::string reasonPart = _rt.Translations.Get("broadcast.punishReason", {{"reason", std::string(reason)}});

    _rt.Messages.Broadcast(std::format("{} {}{}{}", FormatAdminLine(style, adminName, phrase, targetName),
                                       style.PhraseColor, reasonPart, durationSuffix));
}

void ChatService::BroadcastAction(std::string_view translationKey, std::string_view adminName,
                                  std::string_view targetName)
{
    if (!_config.Get().chat.broadcastPunishments)
    {
        return;
    }

    const AdminLineStyle style = BuildStyle(_config.Get().chat);
    auto phrase = BroadcastPhrase(translationKey);
    _rt.Messages.Broadcast(targetName.empty() ? FormatAdminLine(style, adminName, phrase)
                                              : FormatAdminLine(style, adminName, phrase, targetName));
}

void ChatService::BroadcastAction(std::string_view translationKey, std::string_view adminName,
                                  const std::map<std::string, std::string>& nameTokens)
{
    if (!_config.Get().chat.broadcastPunishments)
    {
        return;
    }

    _rt.Messages.Broadcast(
        FormatAdminLine(BuildStyle(_config.Get().chat), adminName, BroadcastPhrase(translationKey), nameTokens));
}

std::string ChatService::BroadcastPhrase(std::string_view translationKey) const
{
    auto phrase = _rt.Translations.Get(translationKey);
    return phrase.empty() ? std::string(translationKey) : phrase;  // Render a missing translation's key literally.
}

std::string ActorName(VoltMod::Runtime& runtime, int slot)
{
    const VoltMod::Player* player = runtime.Players.Get(slot);
    return player ? player->Name() : std::string();
}

}  // namespace AdminSystem::Core
