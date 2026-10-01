#include "Core/PlayerChat.hpp"

#include "Admin/AdminManager.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"
#include "Punishments/PunishmentManager.hpp"

#include <VoltMod/Commands/CommandManager.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Menu/ChatInput.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Messaging/Messages.hpp>
#include <VoltMod/Players/Player.hpp>
#include <VoltMod/Runtime.hpp>
#include <format>
#include <string>

using VoltMod::Player;
using VoltMod::Time;

namespace AdminSystem::Core
{

namespace ChatColors = VoltMod::ChatColors;

/** Localized expiry suffix for mute notices addressed to @p slot. */
static std::string MuteExpiryText(VoltMod::Translations& tr, int64_t expiresAt, int slot)
{
    return Time::FormatExpiry(expiresAt, Time::Now(), tr.Get("muteNotice.permanent", slot),
                              tr.Get("muteNotice.expiresIn", slot));
}

void PlayerChat::ReplyMuteNotice(int slot, std::string_view noticeKey, const std::optional<Database::Punishment>& mute)
{
    auto& tr = _rt.Translations;
    if (!mute)
    {
        _chat.Reply(slot, std::format("{}{}", ChatColors::Red, tr.Get(noticeKey, slot)));
        return;
    }

    _chat.Reply(slot, std::format("{}{}{} {}{}", ChatColors::Red, tr.Get(noticeKey, slot), ChatColors::Default,
                                  ChatColors::Olive, MuteExpiryText(tr, mute->ExpiresAt, slot)));
    if (!mute->Reason.empty())
    {
        _chat.Reply(slot, std::format("{}{}: {}{}", ChatColors::Gray, tr.Get("muteNotice.reason", slot),
                                      ChatColors::Default, mute->Reason));
    }
}

void PlayerChat::RebroadcastAdminChat(const Player* admin, std::string_view message, bool /*teamOnly*/)
{
    if (!admin)
    {
        return;
    }

    auto style = _admins.GetChatStyle(admin->SteamId());

    auto prefixColor = ChatColors::ParseNamed(style.PrefixColor);

    // Hiding the prefix hides the prefix only; the admin's chosen name and message colors stand.
    auto nameColor = ChatColors::ParseNamed(style.NameColor);
    auto messageColor = ChatColors::ParseNamed(style.MessageColor);

    // {prefixColor}{prefix} {nameColor}{name}{Default}: {messageColor}{message}
    std::string line;
    if (style.HasPrefix())
    {
        line = std::format("{}{} {}{}{}: {}{}", prefixColor, style.Prefix, nameColor, admin->Name(),
                           ChatColors::Default, messageColor, message);
    }
    else
    {
        line = std::format("{}{}{}: {}{}", nameColor, admin->Name(), ChatColors::Default, messageColor, message);
    }

    // Team-only filtering isn't implemented yet (no stable team accessor on Player), so admin chat
    // currently broadcasts to everyone regardless of say vs say_team.
    _rt.Messages.Broadcast(line);
}

void PlayerChat::HandleSay(VoltMod::ChatMessage& chat)
{
    const int64_t steamId = chat.Sender.SteamId();
    if (_punishments.IsPunished(Punishments::PunishType::TextMute, steamId))
    {
        const int slot = chat.Sender.Slot();
        if (_textMuteNotice.TryStart(slot, Time::Now()))
        {
            ReplyMuteNotice(slot, "muteNotice.text",
                            _punishments.GetActive(Punishments::PunishType::TextMute, steamId));
        }
        chat.Blocked = true;
        return;
    }

    const auto& chatCfg = _config.Get().chat;
    if (chatCfg.tagAdminChatMessages && _admins.IsAdmin(steamId))
    {
        RebroadcastAdminChat(&chat.Sender, chat.Text, chat.TeamOnly);
        chat.Blocked = true;
    }
}

void PlayerChat::NotifyVoiceMuted(Player* player)
{
    if (!player)
    {
        return;
    }

    int slot = player->Slot();
    if (!_voiceMuteNotice.TryStart(slot, Time::Now()))
    {
        return;
    }

    ReplyMuteNotice(slot, "muteNotice.voice",
                    _punishments.GetActive(Punishments::PunishType::VoiceMute, player->SteamId()));
}

}  // namespace AdminSystem::Core
