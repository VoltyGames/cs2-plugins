#include "Admin/CheatCheck/CheatCheckView.hpp"

#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"

#include <VoltMod/Core/Text/Strings.hpp>
#include <VoltMod/Core/Time/Durations.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Messaging/Messages.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <VoltMod/Ui/Palette.hpp>
#include <format>
#include <string>

namespace AdminSystem::Admin::CheatCheck
{

using VoltMod::Strings;
using VoltMod::Time;
namespace ChatColors = VoltMod::ChatColors;
namespace Palette = VoltMod::Palette;

enum class PanelState
{
    Joined,        // suspect is in the check room; countdown paused
    CreatingRoom,  // awaiting async room creation
    ProvideLink,   // playerProvided mode, suspect hasn't submitted yet
    HasUrl,        // a URL is ready to show
    Generic,       // no URL and nothing pending
};

static PanelState ToPanelState(const PendingCheck& pc)
{
    if (pc.SuspectJoined)
    {
        return PanelState::Joined;
    }
    if (pc.AwaitingUrl)
    {
        return PanelState::CreatingRoom;
    }
    if (pc.Mode == CheatCheckMode::PlayerProvided && pc.ResolvedUrl.empty())
    {
        return PanelState::ProvideLink;
    }
    if (!pc.ResolvedUrl.empty())
    {
        return PanelState::HasUrl;
    }
    return PanelState::Generic;
}

std::string CheatCheckView::PanelHtml(int slot, const PendingCheck& pc) const
{
    if (!_rt.Players.Get(slot))
    {
        return {};
    }

    auto& tr = _rt.Translations;

    int64_t remain = pc.DeadlineSec - Time::Now();
    int remainSec = remain > 0 ? static_cast<int>(remain) : 0;

    const PanelState state = ToPanelState(pc);

    std::string body;
    switch (state)
    {
    case PanelState::Joined:
        body = tr.Get("cheatCheck.joinedPanel", slot);
        break;
    case PanelState::CreatingRoom:
        body = tr.Get("cheatCheck.creatingRoom", slot);
        break;
    case PanelState::ProvideLink:
        body = tr.Get("cheatCheck.provideLink", slot);
        break;
    case PanelState::HasUrl:
        body = std::format("{}<br>{}", tr.Get("cheatCheck.joinHere", slot), Strings::EscapeHtml(pc.ResolvedUrl));
        break;
    case PanelState::Generic:
        body = tr.Get("cheatCheck.instructions", slot);
        break;
    }

    const auto& cfg = _config.Get().cheatCheck;

    // Operator-configured (trusted) banner image rendered atop the panel; CS2 fetches it client-side.
    std::string html;
    if (!cfg.bannerImageUrl.empty())
    {
        html = std::format("<img src='{}' width='{}' height='{}'/><br>", cfg.bannerImageUrl, cfg.bannerWidth,
                           cfg.bannerHeight);
    }

    // Joined pauses the countdown: a calm status line replaces the timer and the kick warning.
    std::string statusLine =
        state == PanelState::Joined
            ? std::format("<font color='{}'>{}</font>", Palette::Success, tr.Get("cheatCheck.joinedStatus", slot))
            : std::format("<font color='{}'>{}: {}s</font>", Palette::Highlight,
                          tr.Get("cheatCheck.timeRemaining", slot), remainSec);

    html += std::format("<font color='{}' size='5'>{}</font><br>{}<br>{}", Palette::Accent,
                        tr.Get("cheatCheck.panelTitle", slot), body, statusLine);

    if ((cfg.autoKick || cfg.autoBan) && state != PanelState::Joined)
    {
        html += std::format("<br><font color='{}'>{}</font>", Palette::AccentBright,
                            tr.Get(cfg.autoBan ? "cheatCheck.willBan" : "cheatCheck.willKick", slot));
    }

    return html;
}

void CheatCheckView::SendInstructions(int slot, const PendingCheck& pc) const
{
    auto& tr = _rt.Translations;

    _chat.Reply(slot, std::format("{}{}", ChatColors::Red, tr.Get("cheatCheck.panelTitle", slot)));

    switch (ToPanelState(pc))
    {
    case PanelState::Joined:
        _chat.Reply(slot, std::format("{}{}", ChatColors::Green, tr.Get("cheatCheck.joinedPanel", slot)));
        break;
    case PanelState::CreatingRoom:
        _chat.Reply(slot, std::format("{}{}", ChatColors::Default, tr.Get("cheatCheck.creatingRoom", slot)));
        break;
    case PanelState::ProvideLink:
        _chat.Reply(slot, std::format("{}{}", ChatColors::Default, tr.Get("cheatCheck.provideLink", slot)));
        break;
    case PanelState::HasUrl:
        _chat.ReplyLink(slot, std::format("{}{}", ChatColors::Default, tr.Get("cheatCheck.joinHere", slot)),
                        pc.ResolvedUrl);
        break;
    case PanelState::Generic:
        break;
    }
}

}  // namespace AdminSystem::Admin::CheatCheck
