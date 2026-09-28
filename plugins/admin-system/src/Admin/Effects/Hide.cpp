#include "Admin/Effects/Descriptors.hpp"

#include <VoltMod/Hooks/GlowVision.hpp>
#include <VoltMod/Hooks/Visibility.hpp>
#include <VoltMod/Runtime.hpp>

namespace AdminSystem::Admin::Effects
{

using Actions::ActionContext;
using VoltMod::Controller;
using VoltMod::GlowVision;
using VoltMod::Team;

// Silent by design (empty On/Off keys): a broadcast would defeat the stealth, and the blanked
// name covers the case where the visibility filter is inert after a CS2 update.

Effect MakeHide(VoltMod::Runtime& runtime)
{
    return Effect{.Permission = Permission::Hide,
                  .Id = EffectId::Hide,
                  .NameKey = "action.hide",
                  .OnKey = "",
                  .OffKey = "",
                  .TickIntervalMs = GlowVision::RefreshIntervalMs,
                  .Setup = [&runtime](const ActionContext& ctx, int) -> EffectInstance {
                      // The controller keeps a team while dead or spectating; the pawn may not exist.
                      const Controller target = ctx.Target().Controller();
                      const Team savedTeam = target.TeamNum();
                      std::string savedName(target.PlayerName());

                      target.SetPlayerName("");
                      target.ChangeTeam(Team::Spectator);

                      int slot = ctx.Target().Slot();
                      auto& visibility = runtime.Visibility;
                      visibility.SetControllerHidden(slot, true);

                      // The tick rebuilds the clones across rounds, spawns and deaths.
                      auto glow = runtime.Visibility.CreateGlow(slot);
                      glow->Refresh();

                      return {.OnTick = [glow]() { glow->Refresh(); },
                              .OnStop =
                                  [&visibility, &entities = runtime.Entities, slot, savedTeam, savedName, glow]() {
                                      glow->Destroy();
                                      visibility.SetControllerHidden(slot, false);
                                      Controller controller = entities.Controller(slot);
                                      if (!controller)
                                      {
                                          return;
                                      }
                                      controller.SetPlayerName(savedName);
                                      // Joining T or CT also ends hide, and that choice wins.
                                      if (savedTeam != Team::Spectator && controller.TeamNum() == Team::Spectator)
                                      {
                                          controller.ChangeTeam(savedTeam);
                                      }
                                  }};
                  }};
}

}  // namespace AdminSystem::Admin::Effects
