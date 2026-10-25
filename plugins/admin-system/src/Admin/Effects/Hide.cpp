#include "Admin/Effects/Descriptors.hpp"

#include <VoltMod/Hooks/GlowVision.hpp>
#include <VoltMod/Hooks/HiddenPlayer.hpp>
#include <VoltMod/Runtime.hpp>
#include <memory>

namespace AdminSystem::Admin::Effects
{

using Actions::ActionContext;
using VoltMod::GlowVision;
using VoltMod::HiddenPlayer;

// Silent by design (empty On/Off keys): a broadcast would defeat the stealth.

Effect MakeHide(VoltMod::Runtime& runtime)
{
    return Effect{.Permission = Permission::Hide,
                  .Id = EffectId::Hide,
                  .NameKey = "action.hide",
                  .OnKey = "",
                  .OffKey = "",
                  .TickIntervalMs = GlowVision::RefreshIntervalMs,
                  .Setup = [&runtime](const ActionContext& ctx, int) -> EffectInstance {
                      auto hidden =
                          std::make_shared<HiddenPlayer>(runtime.Entities, runtime.Visibility, ctx.Target().Slot());
                      return {.OnTick = [hidden] { hidden->UpdateGlow(); }, .OnStop = [hidden] { hidden->Show(); }};
                  }};
}

}  // namespace AdminSystem::Admin::Effects
