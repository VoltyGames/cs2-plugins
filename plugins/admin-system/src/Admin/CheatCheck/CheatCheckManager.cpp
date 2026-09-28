#include "Admin/CheatCheck/CheatCheckManager.hpp"

#include "Admin/Actions/Descriptors.hpp"
#include "Admin/CheatCheck/CheatCheckRoomApi.hpp"
#include "Admin/CheatCheck/CheatCheckView.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Log.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Core/Time/Scheduler.hpp>
#include <VoltMod/Http/HttpClient.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Messaging/Messages.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <format>

namespace AdminSystem::Admin::CheatCheck
{

using VoltMod::Controller;
using VoltMod::Pawn;
using VoltMod::Time;
namespace Log = VoltMod::Log;
namespace ChatColors = VoltMod::ChatColors;

/** CS2 dismisses center HTML on common HUD events, so refresh it every 100 ms. */
static constexpr int PanelRefreshMs = 100;

/** The deadline and the presence poll are both second-granularity, so they need nothing faster. */
static constexpr int DeadlineTickMs = 1000;

static bool IsValidLink(const std::string& link)
{
    if (link.rfind("https://", 0) != 0 && link.rfind("http://", 0) != 0)
    {
        return false;
    }
    // A real URL has no whitespace or HTML-significant characters; reject panel-injection attempts.
    return link.find_first_of(" \t\r\n<>\"'") == std::string::npos;
}

bool CheatCheckManager::StartCheck(int adminSlot, int targetSlot)
{
    if (!ValidSlot(adminSlot) || !ValidSlot(targetSlot))
    {
        return false;
    }

    auto& plrMgr = _rt.Players;
    auto* admin = plrMgr.Get(adminSlot);
    auto* target = plrMgr.Get(targetSlot);
    if (!admin || !target)
    {
        return false;
    }

    Controller targetCtrl = _rt.Entities.Controller(targetSlot);
    const auto& cfg = _config.Get().cheatCheck;

    // A repeated check must restore the original movement/team state.
    const bool wasActive = _checks[targetSlot].Active;
    const VoltMod::MovementFreeze priorFreeze = wasActive ? _checks[targetSlot].Freeze : VoltMod::MovementFreeze{};
    const VoltMod::Team priorTeam =
        wasActive ? _checks[targetSlot].PriorTeam : (cfg.moveToSpectator ? targetCtrl.TeamNum() : VoltMod::Team::None);
    if (wasActive)
    {
        ResetCheck(targetSlot);
    }

    auto& pc = _checks[targetSlot];
    pc.Active = true;
    pc.AdminSlot = adminSlot;
    pc.AdminSteamId = admin->SteamId();
    pc.Mode = ParseMode(cfg.mode);
    pc.DeadlineSec = Time::Now() + cfg.timeoutSec;
    pc.ResolvedUrl.clear();
    pc.AwaitingUrl = false;
    pc.RequestSeq = _seq++;
    pc.Freeze = priorFreeze;
    pc.PriorTeam = priorTeam;

    pc.Freeze.Hold(targetCtrl.Pawn());
    if (cfg.moveToSpectator)
    {
        targetCtrl.ChangeTeam(VoltMod::Team::Spectator);
    }

    pc.DeadlineTimer = _rt.Scheduler.Repeat(DeadlineTickMs, [this, targetSlot] { Tick(targetSlot); });

    ResolveUrl(targetSlot);
    ShowPanel(targetSlot);
    _view.SendInstructions(targetSlot, pc);

    _chat.BroadcastAction("broadcast.cheatCheckCalled", admin->Name(), target->Name());
    return true;
}

void CheatCheckManager::ResolveUrl(int targetSlot)
{
    auto& pc = _checks[targetSlot];
    const auto& cfg = _config.Get().cheatCheck;

    switch (pc.Mode)
    {
    case CheatCheckMode::FixedLink:
        pc.ResolvedUrl = cfg.fixedLink.url;
        break;
    case CheatCheckMode::WebsiteAutoRoom:
        pc.AwaitingUrl = true;
        RequestRoom(targetSlot);
        break;
    case CheatCheckMode::PlayerProvided:
        break;  // the suspect supplies the URL via !cc
    }
}

void CheatCheckManager::RequestRoom(int targetSlot)
{
    auto& pc = _checks[targetSlot];
    auto* target = _rt.Players.Get(targetSlot);

    std::optional<VoltMod::HttpRequest> request;
    if (target)
    {
        auto* admin = _rt.Players.Get(pc.AdminSlot);
        request = BuildRoomRequest(_config.Get().cheatCheck.websiteAutoRoom, target->SteamId(), target->Name(),
                                   pc.AdminSteamId, admin ? admin->Name() : std::string_view{});
    }

    if (!request)
    {
        // StartCheck renders the instructions, so fallback only updates state here.
        FallbackToFixed(pc);
        return;
    }

    const uint64_t seq = pc.RequestSeq;
    _rt.Http.Send(std::move(*request), [this, targetSlot, seq](const VoltMod::HttpResult& result) {
        OnRoomResponse(targetSlot, seq, result);
    });
}

void CheatCheckManager::OnRoomResponse(int targetSlot, uint64_t seq, const VoltMod::HttpResult& result)
{
    if (!ValidSlot(targetSlot))
    {
        return;
    }
    auto& pc = _checks[targetSlot];
    if (!pc.Active || pc.RequestSeq != seq)  // stale: cancelled, expired, re-called, or slot reused
    {
        return;
    }

    const auto& roomCfg = _config.Get().cheatCheck.websiteAutoRoom;
    if (auto urls = ParseRoomResponse(roomCfg, result))
    {
        pc.ResolvedUrl = std::move(urls->PlayerUrl);
        pc.AwaitingUrl = false;

        // Leave RoomCode empty when presence polling is disabled.
        if (!roomCfg.presenceUrl.empty())
        {
            pc.RoomCode = std::move(urls->RoomCode);
            // Delay the first poll by one interval.
            pc.NextPollAtSec = Time::Now() + roomCfg.pollIntervalSec;
        }

        if (!urls->CheckerUrl.empty())
        {
            RelayCheckerUrl(targetSlot, urls->CheckerUrl);
        }
        _view.SendInstructions(targetSlot, pc);
        return;
    }

    if (!result.Ok)
    {
        Log::Warn("Cheat-check room request failed: {}", result.Error);
    }
    else
    {
        Log::Warn("Cheat-check room response rejected (status {}): {}", result.StatusCode, result.Body.substr(0, 300));
    }

    OnRoomFailed(targetSlot);
}

void CheatCheckManager::OnRoomFailed(int targetSlot)
{
    auto& pc = _checks[targetSlot];
    FallbackToFixed(pc);

    ReplyToAdmin(pc, [this, adminSlot = pc.AdminSlot] {
        return std::format("{}{}", ChatColors::Red, _rt.Translations.Get("cheatCheck.apiFailed", adminSlot));
    });

    _view.SendInstructions(targetSlot, pc);
}

void CheatCheckManager::RelayCheckerUrl(int targetSlot, const std::string& checkerUrl)
{
    if (auto slot = ResolveAdminSlot(_checks[targetSlot]))
    {
        _chat.ReplyLink(*slot,
                        std::format("{}{}", ChatColors::Green, _rt.Translations.Get("cheatCheck.checkerUrl", *slot)),
                        checkerUrl);
    }
}

void CheatCheckManager::Tick(int targetSlot)
{
    auto& pc = _checks[targetSlot];
    if (!pc.Active)
    {
        return;
    }

    // Polling continues while the room suspends the deadline.
    if (!pc.SuspectJoined && Time::Now() >= pc.DeadlineSec)
    {
        Expire(targetSlot);
        return;
    }

    PollPresenceIfDue(targetSlot);
}

CheatCheckManager::SubmitResult CheatCheckManager::SubmitPlayerLink(int callerSlot, const std::string& link)
{
    if (!ValidSlot(callerSlot))
    {
        return SubmitResult::NoActiveCheck;
    }

    auto& pc = _checks[callerSlot];
    if (!pc.Active || pc.Mode != CheatCheckMode::PlayerProvided)
    {
        return SubmitResult::NoActiveCheck;
    }

    if (!IsValidLink(link))
    {
        return SubmitResult::Invalid;
    }

    pc.ResolvedUrl = link;

    auto* caller = _rt.Players.Get(callerSlot);
    std::string name = caller ? caller->Name() : std::string();

    if (auto slot = ResolveAdminSlot(pc))
    {
        _chat.ReplyLink(*slot,
                        std::format("{}{} {}{}", ChatColors::Green,
                                    _rt.Translations.Get("cheatCheck.linkReceived", *slot), ChatColors::Default, name),
                        link);
    }

    return SubmitResult::Relayed;
}

void CheatCheckManager::FallbackToFixed(PendingCheck& pc)
{
    pc.AwaitingUrl = false;
    const auto& cfg = _config.Get().cheatCheck;
    if (!cfg.fixedLink.url.empty())
    {
        pc.ResolvedUrl = cfg.fixedLink.url;
    }
}

std::optional<int> CheatCheckManager::ResolveAdminSlot(const PendingCheck& pc) const
{
    if (!_rt.Players.Get(VoltMod::PlayerRef{pc.AdminSlot, pc.AdminSteamId}))
    {
        return std::nullopt;
    }
    return pc.AdminSlot;
}

void CheatCheckManager::ReplyToAdmin(const PendingCheck& pc, const std::function<std::string()>& buildMessage)
{
    if (auto slot = ResolveAdminSlot(pc))
    {
        _chat.Reply(*slot, buildMessage());
    }
}

void CheatCheckManager::ShowPanel(int targetSlot)
{
    // Read _checks on each refresh so state changes appear without a redraw call.
    _panel.Show(targetSlot, PanelRefreshMs, [this](int slot) { return _view.PanelHtml(slot, _checks[slot]); });
}

void CheatCheckManager::ResetCheck(int targetSlot)
{
    _panel.Stop(targetSlot);
    _checks[targetSlot] = PendingCheck{};  // move-assign drops the deadline timer
}

bool CheatCheckManager::Cancel(int adminSlot, int targetSlot)
{
    if (!ValidSlot(targetSlot) || !_checks[targetSlot].Active)
    {
        return false;
    }

    auto* target = _rt.Players.Get(targetSlot);
    std::string targetName = target ? target->Name() : std::string();

    const VoltMod::MovementFreeze freeze = _checks[targetSlot].Freeze;
    const VoltMod::Team restoreTeam = _checks[targetSlot].PriorTeam;
    ResetCheck(targetSlot);
    Unfreeze(targetSlot, freeze, restoreTeam);

    _chat.BroadcastAction("broadcast.cheatCheckCleared", Core::ActorName(_rt, adminSlot), targetName);
    return true;
}

void CheatCheckManager::Expire(int targetSlot)
{
    const auto& cfg = _config.Get().cheatCheck;

    auto* target = _rt.Players.Get(targetSlot);
    std::string targetName = target ? target->Name() : std::string();

    const VoltMod::MovementFreeze freeze = _checks[targetSlot].Freeze;
    const VoltMod::Team restoreTeam = _checks[targetSlot].PriorTeam;
    const int64_t adminSteamId = _checks[targetSlot].AdminSteamId;
    ResetCheck(targetSlot);  // deactivate before the kick triggers disconnect cleanup

    if (cfg.autoBan && target)
    {
        Database::Punishment ban{.Kind = Punishments::PunishType::Ban,
                                 .TargetSteamId = target->SteamId(),
                                 .TargetName = targetName,
                                 .AdminSteamId = adminSteamId,
                                 .AdminName = _punishments.AdminDisplayName(adminSteamId),
                                 .Reason = cfg.kickReason,
                                 .Duration = cfg.banDurationSec};
        _punishments.Issue(ban);
    }
    else if (cfg.autoKick)
    {
        _rt.Entities.Controller(targetSlot).Kick(cfg.kickReason);
    }
    else
    {
        Unfreeze(targetSlot, freeze, restoreTeam);
    }

    _chat.BroadcastAction("broadcast.cheatCheckTimedOut", {}, {{"player", targetName}});
}

void CheatCheckManager::Unfreeze(int targetSlot, VoltMod::MovementFreeze freeze, VoltMod::Team restoreTeam)
{
    Controller controller = _rt.Entities.Controller(targetSlot);
    if (!controller)
    {
        return;
    }
    // Set only when the check pulled the player to spectator.
    if (VoltMod::IsPlaying(restoreTeam))
    {
        controller.ChangeTeam(restoreTeam);
    }
    freeze.Release(controller.Pawn());
}

void CheatCheckManager::CancelAllForSlot(int slot)
{
    if (ValidSlot(slot) && _checks[slot].Active)
    {
        ResetCheck(slot);  // silent: the player is gone, no unfreeze/broadcast
    }
}

void CheatCheckManager::CancelAll()
{
    for (int slot = 0; slot < MaxSlots; ++slot)
    {
        if (!_checks[slot].Active)
        {
            continue;
        }
        Unfreeze(slot, _checks[slot].Freeze, _checks[slot].PriorTeam);
        ResetCheck(slot);
    }
}

}  // namespace AdminSystem::Admin::CheatCheck
