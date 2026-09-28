#include "Admin/Actions/Descriptors.hpp"

namespace AdminSystem::Admin::Actions
{

const Action Kill{Permission::Control, /*requireAlive*/ true, [](const ActionContext& ctx) -> OptKey {
                      ctx.Target().Pawn().Slay();
                      return "broadcast.killed";
                  }};

const Action Godmode{Permission::Health, /*requireAlive*/ true, [](const ActionContext& ctx) -> OptKey {
                         const VoltMod::Pawn pawn = ctx.Target().Pawn();
                         const bool on = !pawn.Godmode();
                         pawn.SetGodmode(on);
                         return on ? "broadcast.godmodeOn" : "broadcast.godmodeOff";
                     }};

const ParamAction SetHealth{Permission::Health, /*requireAlive*/ true,
                            [](const ActionContext& ctx, int health) -> OptKey {
                                ctx.Target().Pawn().SetHealth(health);
                                return "broadcast.healed";
                            }};

const ParamAction SetArmor{Permission::Health, /*requireAlive*/ true,
                           [](const ActionContext& ctx, int armor) -> OptKey {
                               ctx.Target().Pawn().SetArmorValue(armor);
                               return "broadcast.armored";
                           }};

const ParamAction SetSize{Permission::Fun, /*requireAlive*/ true, [](const ActionContext& ctx, int percent) -> OptKey {
                              ctx.Target().Pawn().SetScale(percent / 100.0f);
                              return "broadcast.sizeSet";
                          }};

}  // namespace AdminSystem::Admin::Actions
