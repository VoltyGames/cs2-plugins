#include "Descriptors.hpp"

#include <optional>

namespace AdminSystem::Admin::Actions
{

using VoltMod::Schema::MoveType_t;

static constexpr float BuryDepth = 15.0f;

/** Switch between @p type and walking; true when @p type is now on. */
static bool ToggleMoveType(const VoltMod::Pawn& pawn, MoveType_t type)
{
    const bool on = pawn.MoveType() != type;
    pawn.SetMoveType(on ? type : MoveType_t::MOVETYPE_WALK);
    return on;
}

static void ShiftUp(const VoltMod::Pawn& pawn, float height)
{
    Vector origin = pawn.Origin();
    origin.z += height;
    pawn.Teleport(origin, std::nullopt, std::nullopt);
}

const Action Noclip{Permission::Control, /*requireAlive*/ false, [](const ActionContext& ctx) -> OptKey {
                        return ToggleMoveType(ctx.Target().Pawn(), MoveType_t::MOVETYPE_NOCLIP) ? "broadcast.noclipOn"
                                                                                                : "broadcast.noclipOff";
                    }};

const Action Freeze{Permission::Control, /*requireAlive*/ false, [](const ActionContext& ctx) -> OptKey {
                        return ToggleMoveType(ctx.Target().Pawn(), MoveType_t::MOVETYPE_NONE) ? "broadcast.freezeOn"
                                                                                              : "broadcast.freezeOff";
                    }};

const Action Bury{Permission::Control, /*requireAlive*/ true, [](const ActionContext& ctx) -> OptKey {
                      ShiftUp(ctx.Target().Pawn(), -BuryDepth);
                      return "broadcast.buried";
                  }};

const Action Unbury{Permission::Control, /*requireAlive*/ true, [](const ActionContext& ctx) -> OptKey {
                        ShiftUp(ctx.Target().Pawn(), BuryDepth);
                        return "broadcast.unburied";
                    }};

const ParamAction SetSpeed{Permission::Control, /*requireAlive*/ true,
                           [](const ActionContext& ctx, int percent) -> OptKey {
                               ctx.Target().Pawn().SetVelocityModifier(percent / 100.0f);
                               return "broadcast.speedSet";
                           }};

}  // namespace AdminSystem::Admin::Actions
