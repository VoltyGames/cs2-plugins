#include "Admin/Effects/Model.hpp"

#include "Admin/Effects/Descriptors.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Runtime.hpp>
#include <string_view>

namespace AdminSystem::Admin::Effects
{

using Actions::ActionContext;
using VoltMod::Pawn;

// Restore live players to a base team model; respawn restores their selected agent.
static constexpr std::string_view DefaultModelT = "characters/models/tm_phoenix/tm_phoenix.vmdl";
static constexpr std::string_view DefaultModelCt = "characters/models/ctm_sas/ctm_sas.vmdl";

// Spectators and unassigned players have no restore model; SetModel ignores the empty view.
static std::string_view DefaultModelForTeam(VoltMod::Team team)
{
    if (team == VoltMod::Team::T)
    {
        return DefaultModelT;
    }
    if (team == VoltMod::Team::CT)
    {
        return DefaultModelCt;
    }
    return {};
}

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

    runtime.Precache.Add(DefaultModelT);
    runtime.Precache.Add(DefaultModelCt);
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
                      ctx.Target().Pawn().SetModel(FunModels()[param].Path);

                      // EffectManager cancels any prior Model effect first (re-select swaps); OnStop restores the
                      // team default when cleared while alive (a no-op on death, where IsAlive is false).
                      int targetSlot = ctx.Target().Slot();
                      return {.OnStop = [&entities = runtime.Entities, targetSlot]() {
                          const Pawn pawn = entities.Pawn(targetSlot);
                          if (pawn.IsAlive())
                          {
                              pawn.SetModel(DefaultModelForTeam(pawn.TeamNum()));
                          }
                      }};
                  }};
}

}  // namespace AdminSystem::Admin::Effects
