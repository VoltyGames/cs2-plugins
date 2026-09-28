#include "App.hpp"
#include "Commands/Commands.hpp"
#include "Reports/ReportFlow.hpp"
#include "Reports/ReportManager.hpp"

#include <VoltMod/Api.hpp>
#include <string>

using VoltMod::Caller;
using VoltMod::Reply;
using VoltMod::Result;

namespace AdminSystem::Commands
{

using AdminSystem::Reports::ReportDenial;

void RegisterReportCommand(VoltMod::CommandManager& commands, App& app)
{
    // No permission - reporting is open to every player. No arguments either: the menu is the
    // only entry point, so a typed target or reason is deliberately unsupported.
    commands.Add("report")
        .Alias("r")
        .Describe("Report a player to the server staff.")
        .Run([&app](Caller c) -> Result<Reply> {
            // Fail before opening a menu; the flow re-runs the full gate before
            // it writes.
            const auto gate = app.Reports.CanReport(c.Player->SteamId());
            switch (gate.Reason)
            {
            case ReportDenial::Disabled:
                return c.Fail("report.disabled");
            case ReportDenial::OnCooldown:
                return c.Fail("report.cooldown", {{"seconds", std::to_string(gate.SecondsLeft)}});
            default:
                break;
            }

            app.ReportMenu.Open(c.Slot);
            return Reply::Silent();
        });
}

}  // namespace AdminSystem::Commands
