#pragma once

#include "Admin/CheatCheck/CheatCheckView.hpp"
#include "Admin/CheatCheck/PendingCheck.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"
#include "Punishments/PunishmentManager.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Entities/Entity.hpp>
#include <VoltMod/Http/HttpResult.hpp>
#include <VoltMod/Messaging/CenterHtml.hpp>
#include <VoltMod/Schema/Generated/Enums.hpp>
#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>

namespace AdminSystem::Admin::CheatCheck
{

constexpr int MaxSlots = VoltMod::MaxPlayers;

/**
 * Owns pending checks, including the freeze, center-HTML panel, countdown, and timeout action.
 * Methods run on the game thread; HTTP completions are dispatched there before they arrive here.
 */
class CheatCheckManager
{
public:
    CheatCheckManager(VoltMod::Runtime& runtime, const Config::ConfigManager& config, Core::ChatService& chat,
                      Punishments::PunishmentManager& punishments)
        : _rt(runtime), _config(config), _chat(chat), _punishments(punishments)
    {}

    enum class SubmitResult
    {
        NoActiveCheck,
        Invalid,
        Relayed,
    };

    /** Start a check on `targetSlot` called by `adminSlot`. Re-call replaces any existing check. */
    bool StartCheck(int adminSlot, int targetSlot);

    /** Cancel a check, unfreeze the suspect, clear its panel, and broadcast who cleared it.
     *  Returns false if inactive. */
    bool Cancel(int adminSlot, int targetSlot);

    /** True while a check is pending on `slot` (drives menu enablement). */
    bool IsActive(int slot) const { return ValidSlot(slot) && _checks[slot].Active; }

    /** A suspect submitted a link via `!cc` (playerProvided mode). */
    SubmitResult SubmitPlayerLink(int callerSlot, const std::string& link);

    /** Remove a disconnecting slot without unfreezing or broadcasting. */
    void CancelAllForSlot(int slot);

    /** Remove every active check during plugin unload. */
    void CancelAll();

private:
    VoltMod::Runtime& _rt;
    const Config::ConfigManager& _config;
    Core::ChatService& _chat;
    Punishments::PunishmentManager& _punishments;
    CheatCheckView _view{_rt, _config, _chat};
    /** Panel refresh loop. Declared after _view because its callback reads through it. */
    VoltMod::CenterHtml _panel{_rt.Messages, _rt.Scheduler, _rt.Slots};

    void Tick(int targetSlot);
    void Expire(int targetSlot);
    void ShowPanel(int targetSlot);   // start (or restart) the panel's own refresh loop
    void ResetCheck(int targetSlot);  // cancel timer + clear panel + reset state, silently
    void Unfreeze(int targetSlot, VoltMod::MovementFreeze freeze, VoltMod::Team restoreTeam);
    void ResolveUrl(int targetSlot);
    void RequestRoom(int targetSlot);
    void OnRoomResponse(int targetSlot, uint64_t seq, const VoltMod::HttpResult& result);
    void OnRoomFailed(int targetSlot);
    void RelayCheckerUrl(int targetSlot, const std::string& checkerUrl);

    // Presence polling pauses the countdown while the suspect is in the check room.
    void PollPresenceIfDue(int targetSlot);
    void OnPresenceResponse(int targetSlot, uint64_t seq, const VoltMod::HttpResult& result);

    void FallbackToFixed(PendingCheck& pc);  // drop awaiting state, use the configured fixed link if any

    // Nullopt when the calling admin disconnected or the slot was reused.
    std::optional<int> ResolveAdminSlot(const PendingCheck& pc) const;

    // Reply only while the calling admin still occupies the recorded slot.
    void ReplyToAdmin(const PendingCheck& pc, const std::function<std::string()>& buildMessage);

    bool ValidSlot(int slot) const { return slot >= 0 && slot < MaxSlots; }

    std::array<PendingCheck, MaxSlots> _checks{};
    uint64_t _seq = 1;
};

}  // namespace AdminSystem::Admin::CheatCheck
