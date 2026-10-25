#pragma once

#include "Admin/Menu/MenuCatalog.hpp"
#include "App.hpp"
#include "Core/Permissions.hpp"

#include <VoltMod/Menu/MenuModel.hpp>
#include <VoltMod/Runtime.hpp>
#include <functional>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace AdminSystem::Admin::Menu
{

/** Whether @p slot still holds @p permission. A permission may have been revoked (e.g. by
 *  !admin_reload) while the menu was open. */
inline bool MayUse(App& app, int slot, std::string_view permission)
{
    auto& players = app.Runtime.Players;
    return app.Runtime.Policy.Authorize(players.GetRef(slot), std::nullopt, permission).has_value();
}

/** @ref MayUse as a row's condition: asked on every redraw, and it refuses the press itself, so
 *  no handler repeats the check. */
inline VoltMod::EnabledCondition Allows(App& app, std::string_view permission)
{
    return VoltMod::EnabledCondition([&app, permission](int slot) { return MayUse(app, slot, permission); });
}

/** @ref MayUse as a flow validator, for the one player the flow runs for. */
inline auto RequirePermission(App& app, std::string_view permission, int slot)
{
    return [&app, permission, slot](const auto&) -> std::optional<std::string> {
        if (!MayUse(app, slot, permission))
        {
            return "punish.notAllowed";
        }
        return std::nullopt;
    };
}

/** Whether @p adminSlot may see @p row at all. Permission only: a row that is merely unusable
 *  right now stays visible and greys itself, so rows do not appear and vanish under the cursor. */
bool Visible(App& app, int adminSlot, const RowSpec& row);

/** Whether any of @p rows is visible to @p adminSlot. Walks permission strings, building no
 *  child menu. */
bool AnyVisible(App& app, int adminSlot, std::span<const RowSpec> rows);

/** @p item greyed out, showing @p reason, whenever @p usable says no. No row spec exposes
 *  `MenuRow::Value`, so the reason is folded into `Describe`; activation, stepping and commit are
 *  wrapped too, or a greyed preset row would still change its value. */
VoltMod::MenuItem DisableUnless(VoltMod::MenuItem item, std::function<bool(int slot)> usable, std::string reason);

/** @ref DisableUnless for an action whose descriptor refuses a dead target; the dispatcher skips
 *  those silently, so the row would otherwise look live and do nothing. */
VoltMod::MenuItem WhileAlive(App& app, int adminSlot, VoltMod::PlayerRef target, VoltMod::MenuItem item);

/** Warn about any row whose catalog permission differs from the one its descriptor runs on. */
void VerifyCatalog(App& app);

}  // namespace AdminSystem::Admin::Menu
