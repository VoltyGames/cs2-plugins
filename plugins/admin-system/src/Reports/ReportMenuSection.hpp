#pragma once

#include "Config/ConfigManager.hpp"
#include "Reports/ReportFlow.hpp"
#include "Reports/ReportManager.hpp"

#include <Contracts/IMenuSection.hpp>
#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Signals/Subscription.hpp>

namespace AdminSystem::Reports
{

/** The main menu's "report" entry: shown while reports are on, opens the `!report` player picker. */
class ReportMenuSection final : public Contracts::IMenuSection
{
public:
    ReportMenuSection(VoltMod::Runtime& runtime, const Config::ConfigManager& settings, ReportManager& reports,
                      ReportFlow& flow)
        : _runtime(runtime), _settings(settings), _reports(reports), _flow(flow)
    {}

    /** Offer this to other plugins until this is destroyed. */
    void Publish();

    bool IsVisibleTo(int slot) override;
    bool Open(int slot) override;

private:
    VoltMod::Runtime& _runtime;
    const Config::ConfigManager& _settings;
    ReportManager& _reports;
    ReportFlow& _flow;
    /** Declared last, so the entry is withdrawn before anything it reaches. */
    VoltMod::Subscription _published;
};

}  // namespace AdminSystem::Reports
