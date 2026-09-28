#include "Reports/ReportMenuSection.hpp"

#include "Reports/ReportFlow.hpp"
#include "Reports/ReportManager.hpp"

#include <VoltMod/Api.hpp>
#include <string>

namespace AdminSystem::Reports
{

void ReportMenuSection::Publish()
{
    _published = _runtime.Exchange.Publish<Contracts::IMenuSection>(this, "report");
}

bool ReportMenuSection::IsVisibleTo(int slot)
{
    return _runtime.Players.Get(slot) && _settings.Get().reports.enabled;
}

bool ReportMenuSection::Open(int slot)
{
    const VoltMod::Player* player = _runtime.Players.Get(slot);
    if (!player)
    {
        return false;
    }

    // The same gate as `!report`, so the menu entry and the command refuse alike.
    const ReportGate gate = _reports.CanReport(player->SteamId());
    if (gate.Reason == ReportDenial::OnCooldown)
    {
        _runtime.Messages.SendKey(slot, "report.cooldown", {{"seconds", std::to_string(gate.SecondsLeft)}});
        return true;
    }
    if (!gate)
    {
        return false;
    }

    _flow.Open(slot);
    return true;
}

}  // namespace AdminSystem::Reports
