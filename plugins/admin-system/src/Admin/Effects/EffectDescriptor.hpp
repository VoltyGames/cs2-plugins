#pragma once

#include "Admin/Actions/ActionContext.hpp"
#include "Admin/Effects/EffectManager.hpp"

#include <functional>
#include <string>
#include <vector>

namespace AdminSystem::Admin::Effects
{

/** One selectable option for an @ref EffectDescriptor picker submenu (@ref EffectDescriptor::Choices). */
struct EffectChoice
{
    std::string Label;
    int Param;
};

/**
 * @brief A toggle / one-shot / timed / parameterized player effect expressed as data, mirroring
 * @ref Actions::Action.
 *
 * `Setup` receives the resolved, permission/immunity-checked context plus a caller-supplied `param`
 * (0 for a plain toggle; a picker index for a parameterized effect - see @ref Choices), applies the
 * effect, and returns its @ref EffectInstance. Lifetime is declarative: `Scope`, `TickIntervalMs`,
 * and `DurationMs` are forwarded to @ref EffectManager::Apply. An empty `OnKey`/`OffKey` suppresses
 * that broadcast. Dispatch via @ref EffectDispatcher, which applies `Policy::Authorize` before
 * running the body.
 *
 * Leave @ref Choices empty for a plain toggle row (@ref Menu::ActionRows::Effect); set it to drive
 * a picker submenu (@ref Menu::ActionRows::EffectPicker), where each @ref EffectChoice's `Param` is
 * what `Setup` receives.
 */
struct EffectDescriptor
{
    std::string Permission; /**< Permission token; "" skips the check. */
    EffectId Id;
    std::string NameKey;       /**< Translation key for the menu row label. */
    std::string OnKey;         /**< Broadcast key when applied ("" = silent). */
    std::string OffKey;        /**< Broadcast key when cleared ("" = silent). */
    std::string ResetLabelKey; /**< Picker only; "" = no reset row. */
    EffectScope Scope = EffectScope::Persistent;
    int TickIntervalMs = 0;
    int DurationMs = 0;
    bool RequireAlive = false;
    /** Empty = plain toggle; non-empty drives a picker submenu whose rows are these choices. */
    std::function<std::vector<EffectChoice>()> Choices;
    std::function<EffectInstance(const Actions::ActionContext&, int param)> Setup;
};

}  // namespace AdminSystem::Admin::Effects
