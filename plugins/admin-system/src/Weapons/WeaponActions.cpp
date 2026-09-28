#include "WeaponActions.hpp"

#include "Admin/Actions/ActionContext.hpp"
#include "App.hpp"
#include "Core/Permissions.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Runtime.hpp>
#include <functional>
#include <string>
#include <string_view>

namespace AdminSystem::Weapons
{

using Admin::Actions::Action;
using Admin::Actions::ActionContext;
using Admin::Actions::OptKey;

/**
 * Run @p body under the weapon permission and the shared broadcast policy.
 *
 * `RequireAlive` is left off and the aliveness check done here instead, because the dispatcher
 * skips a dead target silently and the chat commands need to say why nothing happened.
 */
static WeaponActionResult RunWeaponAction(App& app, VoltMod::PlayerRef admin, VoltMod::PlayerRef target,
                                          const std::function<bool(const ActionContext&)>& body,
                                          std::string_view broadcastKey)
{
    auto outcome = WeaponActionResult::NotAllowed;

    app.Actions.Run(
        admin, target,
        Action{
            .Permission = Permission::Weapon, .RequireAlive = false, .Body = [&](const ActionContext& ctx) -> OptKey {
                if (!ctx.Target().Pawn().IsAlive())
                {
                    outcome = WeaponActionResult::TargetDead;
                    return std::nullopt;
                }
                if (!body(ctx))
                {
                    outcome = WeaponActionResult::EngineRefused;
                    return std::nullopt;
                }
                outcome = WeaponActionResult::Ok;
                return std::string(broadcastKey);
            }});

    return outcome;
}

WeaponActionResult GiveWeapon(App& app, VoltMod::PlayerRef admin, VoltMod::PlayerRef target, std::string_view item)
{
    const std::string classname(item);
    return RunWeaponAction(
        app, admin, target, [&classname](const ActionContext& ctx) { return static_cast<bool>(ctx.Target().Pawn().GiveItem(classname)); },
        "broadcast.gaveWeapon");
}

WeaponActionResult StripWeapons(App& app, VoltMod::PlayerRef admin, VoltMod::PlayerRef target)
{
    return RunWeaponAction(
        app, admin, target, [](const ActionContext& ctx) { return ctx.Target().Pawn().StripWeapons(); },
        "broadcast.stripped");
}

}  // namespace AdminSystem::Weapons
