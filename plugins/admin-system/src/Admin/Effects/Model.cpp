#include "Admin/Effects/Model.hpp"

#include "Admin/Effects/Descriptors.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Runtime.hpp>
#include <string>
#include <utility>

namespace AdminSystem::Admin::Effects
{

using Actions::ActionContext;
using VoltMod::Pawn;

const std::vector<FunModel>& FunModels()
{
    // Use always-mounted assets so every vanilla map can render these models.
    static const std::vector<FunModel> models = {
        {"Chicken", std::string(ChickenModelPath)},
        {"Fire Hydrant", "models/props_street/firehydrant.vmdl"},
        {"C4 Bomb", "weapons/models/c4/weapon_c4.vmdl"},
    };
    return models;
}

void PrecacheModels(VoltMod::Runtime& runtime)
{
    for (const auto& model : FunModels())
    {
        runtime.Precache.Add(model.Path);
    }
}

Effect MakeModel(VoltMod::Runtime& runtime)
{
    return Effect{.Permission = Permission::Fun,
                  .Id = EffectId::Model,
                  .NameKey = "action.model",
                  .OnKey = "broadcast.modelOn",
                  .OffKey = "broadcast.modelOff",
                  .ResetLabelKey = "action.modelReset",
                  .RequireAlive = true,
                  .Choices =
                      []() {
                          std::vector<EffectChoice> choices;
                          const auto& models = FunModels();
                          choices.reserve(models.size());
                          for (int i = 0; i < static_cast<int>(models.size()); ++i)
                          {
                              choices.push_back({models[i].Name, i});
                          }
                          return choices;
                      },
                  .Setup = [&runtime](const ActionContext& ctx, int param) -> EffectInstance {
                      // Dispatch already bounds-checked param and required the target alive.
                      const Pawn target = ctx.Target().Pawn();
                      std::string ownModel = target.ModelName();
                      target.SetModel(FunModels()[param].Path);

                      // EffectManager cancels any prior Model effect first, so ownModel is never a fun model.
                      // Clearing on death does nothing: the respawn brings the player's agent back.
                      int targetSlot = ctx.Target().Slot();
                      return {.OnStop = [&entities = runtime.Entities, targetSlot, ownModel = std::move(ownModel)]() {
                          const Pawn pawn = entities.Pawn(targetSlot);
                          if (pawn.IsAlive())
                          {
                              pawn.SetModel(ownModel);
                          }
                      }};
                  }};
}

}  // namespace AdminSystem::Admin::Effects
