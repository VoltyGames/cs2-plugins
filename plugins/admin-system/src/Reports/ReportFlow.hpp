#pragma once

#include "Config/ConfigManager.hpp"
#include "Reports/ReportManager.hpp"

#include <VoltMod/Api.hpp>
#include <optional>
#include <string>

namespace AdminSystem::Reports
{

/**
 * Everything a report accumulates while the reporter walks target -> reason -> confirm.
 * Copied by value through the menu callbacks.
 */
struct PendingReport
{
    /** Captured at selection and re-verified at every step, so slot reuse can't redirect the
     *  report; the name is resolved fresh at display time rather than carried here stale. */
    VoltMod::PlayerRef Target;
    std::string ReasonCode;
    std::string ReasonText;
};

/** The `!report` menus: player picker, reason, confirm. */
class ReportFlow
{
public:
    ReportFlow(VoltMod::Runtime& runtime, const Config::ConfigManager& settings, ReportManager& reports)
        : _runtime(runtime), _settings(settings), _reports(reports)
    {}

    /** Open the report player picker for @p reporterSlot. */
    void Open(int reporterSlot);

private:
    void Start(int reporterSlot, VoltMod::PlayerRef targetRef);
    std::optional<std::string> Validate(int slot, const PendingReport& pending);
    void Submit(int reporterSlot, PendingReport& pending);

    VoltMod::Runtime& _runtime;
    const Config::ConfigManager& _settings;
    ReportManager& _reports;
};

}  // namespace AdminSystem::Reports
