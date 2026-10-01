#pragma once

#include "Admin/AdminManager.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"
#include "Punishments/PunishmentManager.hpp"

#include <VoltMod/Core/Signals/Subscription.hpp>
#include <VoltMod/Core/Time/Cooldown.hpp>
#include <VoltMod/Players/Player.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <cstdint>
#include <optional>
#include <string_view>

namespace AdminSystem::Core
{

/**
 * The inbound half of chat: what a player says, and what they are allowed to say.
 *
 * Split from @ref ChatService because this side reads admin and punishment state while the
 * output side is read by those same managers - keeping both in one class made the object graph
 * cyclic. Constructed after them, so it holds them directly.
 */
class PlayerChat
{
public:
    /** Subscribes to every chat line no menu or command took. */
    PlayerChat(VoltMod::Runtime& runtime, const Config::ConfigManager& config, ChatService& chat,
               Admin::AdminManager& admins, Punishments::PunishmentManager& punishments)
        : _rt(runtime), _config(config), _chat(chat), _admins(admins), _punishments(punishments)
    {
        _said = _rt.Players.Said += [this](VoltMod::ChatMessage& chat) { HandleSay(chat); };
    }

    /**
     * Re-emit an admin's regular chat with their group's colored prefix attached.
     * Caller is expected to SUPERCEDE the original say/say_team in the chat hook.
     */
    void RebroadcastAdminChat(const VoltMod::Player* admin, std::string_view message, bool teamOnly);

    /**
     * Notify a voice-muted player that the engine is suppressing their microphone. Rate-limited
     * to avoid spam: the SetClientListening hook fires once per (receiver, sender) pair every
     * time the player keys voice, which can easily hit dozens of calls in a single press.
     */
    void NotifyVoiceMuted(VoltMod::Player* player);

private:
    /** Block a text-muted player's line, and rebroadcast admin chat with a colored prefix in
     *  place of the original. */
    void HandleSay(VoltMod::ChatMessage& chat);

    VoltMod::Runtime& _rt;
    const Config::ConfigManager& _config;
    ChatService& _chat;
    Admin::AdminManager& _admins;
    Punishments::PunishmentManager& _punishments;

    // Once per minute per player: the voice hook fires every keypress and chat spam produces
    // dozens of say events, so unthrottled notices would out-spam the spam itself.
    static constexpr int64_t MuteNoticeIntervalSec = 60;

    /** The red "you are muted" line, plus the expiry and reason when the mute row is in hand. */
    void ReplyMuteNotice(int slot, std::string_view noticeKey, const std::optional<Database::Punishment>& mute);

    VoltMod::Cooldown<int> _voiceMuteNotice{MuteNoticeIntervalSec};
    VoltMod::Cooldown<int> _textMuteNotice{MuteNoticeIntervalSec};

    /** Declared last so the handler stops before the state it captures. */
    VoltMod::Subscription _said;
};

}  // namespace AdminSystem::Core
