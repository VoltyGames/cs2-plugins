#include "Admin/Menu/Pickers/SwapPartnerPicker.hpp"

#include "Admin/Actions/Descriptors.hpp"
#include "Admin/Menu/Pickers/PlayerPicker.hpp"
#include "App.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Entities/EntitySystem.hpp>
#include <VoltMod/Entities/Pawn.hpp>
#include <VoltMod/Runtime.hpp>

namespace AdminSystem::Admin::Menu
{

std::shared_ptr<VoltMod::Menu> BuildSwapPartnerPicker(const MenuContext& ctx, VoltMod::PlayerRef first)
{
    App& app = ctx.Plugin;
    const int adminSlot = ctx.Admin.Slot;

    return BuildPlayerPicker(app, adminSlot,
                             {.Title = ctx.Translate("common.selectSwapTarget"),
                              .Pick =
                                  [&app, adminSlot, first](VoltMod::PlayerRef second) {
                                      Actions::Swap(app, app.Runtime.Players.GetRef(adminSlot), first, second);
                                      app.Runtime.Menus.CloseAll(adminSlot);
                                  },
                              .Enabled =
                                  [&entities = app.Runtime.Entities, first](VoltMod::PlayerRef candidate) {
                                      // Gray out partners Swap would reject: the already-picked player and the dead.
                                      return candidate.Slot != first.Slot && entities.Pawn(candidate.Slot).IsAlive();
                                  }});
}

}  // namespace AdminSystem::Admin::Menu
