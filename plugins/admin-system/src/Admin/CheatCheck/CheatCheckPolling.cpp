#include "Admin/CheatCheck/CheatCheckManager.hpp"
#include "Admin/CheatCheck/CheatCheckRoomApi.hpp"
#include "Admin/CheatCheck/CheatCheckView.hpp"
#include "Config/ConfigManager.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Log.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Http/HttpClient.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <algorithm>
#include <format>

namespace AdminSystem::Admin::CheatCheck
{

using VoltMod::Time;
namespace Log = VoltMod::Log;
namespace ChatColors = VoltMod::ChatColors;

// A site blip can briefly report a joined suspect as absent; never resume with less than this,
// so they aren't kicked before the next poll can correct the picture.
static constexpr int64_t MinResumeSec = 15;

void CheatCheckManager::PollPresenceIfDue(int targetSlot)
{
    auto& pc = _checks[targetSlot];
    const bool due = !pc.RoomCode.empty() && !pc.PollInFlight && Time::Now() >= pc.NextPollAtSec;
    if (!due)
    {
        return;
    }

    auto* target = _rt.Players.Get(targetSlot);
    if (!target)
    {
        return;  // disconnect cleanup tears the check down
    }

    const auto& cfg = _config.Get().cheatCheck.websiteAutoRoom;
    auto request = BuildPresenceRequest(cfg, pc.RoomCode, target->SteamId());
    if (!request)
    {
        // presenceUrl was removed by a config reload mid-check; back off a full interval
        // instead of re-attempting every tick.
        pc.NextPollAtSec = Time::Now() + cfg.pollIntervalSec;
        return;
    }

    pc.PollInFlight = true;
    const uint64_t seq = pc.RequestSeq;
    _rt.Http.Send(std::move(*request), [this, targetSlot, seq](const VoltMod::HttpResult& result) {
        OnPresenceResponse(targetSlot, seq, result);
    });
}

void CheatCheckManager::OnPresenceResponse(int targetSlot, uint64_t seq, const VoltMod::HttpResult& result)
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

    const auto& cfg = _config.Get().cheatCheck.websiteAutoRoom;
    pc.PollInFlight = false;
    pc.NextPollAtSec = Time::Now() + cfg.pollIntervalSec;

    auto* target = _rt.Players.Get(targetSlot);
    const auto present = target ? ParsePresence(cfg, result, target->SteamId()) : std::nullopt;
    if (!present)
    {
        // Fail-open: an unreachable/failing presence API keeps the current state (the countdown
        // runs as before a join; a paused check stays paused until the admin resolves it).
        Log::Warn("Cheat-check presence poll failed for room {}: {}", pc.RoomCode,
                  result.Ok ? std::format("status {}", result.StatusCode) : result.Error);
        return;
    }

    if (*present == pc.SuspectJoined)
    {
        return;
    }

    const std::string targetName = target ? target->Name() : std::string();

    if (*present)
    {
        pc.SuspectJoined = true;
        pc.PausedRemainingSec = std::max<int64_t>(pc.DeadlineSec - Time::Now(), 0);
        ReplyToAdmin(pc, [this, &targetName, adminSlot = pc.AdminSlot] {
            return std::format("{}{}", ChatColors::Green,
                               _rt.Translations.Get("cheatCheck.suspectJoined", adminSlot, {{"name", targetName}}));
        });
    }
    else
    {
        pc.SuspectJoined = false;
        pc.DeadlineSec = Time::Now() + std::max(pc.PausedRemainingSec, MinResumeSec);
        ReplyToAdmin(pc, [this, &targetName, adminSlot = pc.AdminSlot] {
            return std::format("{}{}", ChatColors::Red,
                               _rt.Translations.Get("cheatCheck.suspectLeft", adminSlot, {{"name", targetName}}));
        });
    }
}

}  // namespace AdminSystem::Admin::CheatCheck
