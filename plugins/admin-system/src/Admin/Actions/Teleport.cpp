#include "Admin/Actions/Descriptors.hpp"
#include "App.hpp"
#include "Core/ChatService.hpp"

#include <VoltMod/Engine/Math.hpp>
#include <optional>

namespace AdminSystem::Admin::Actions
{

// Clears the ~32-unit player hull, so two players teleported together do not stick.
static constexpr float TeleportClearance = 48.0f;

/** A spot ahead of @p anchor along its level aim, at the anchor's height. */
static Vector ClearedDestination(const VoltMod::Pawn& anchor)
{
    return anchor.Origin() + VoltMod::YawToForward(anchor.EyeAngles().y) * TeleportClearance;
}

/** Two-target broadcast: the phrase receives the target names as {a} and {b}. Swap is the only
 *  action that resolves a pair, so this stays local to it. */
static void BroadcastPair(App& app, const ActionContext& first, const ActionContext& second, const std::string& key)
{
    app.Chat.BroadcastAction(key, first.Caller().Name(), {{"a", first.Target().Name()}, {"b", second.Target().Name()}});
}

const Action Bring{Permission::Control, /*requireAlive*/ true, [](const ActionContext& ctx) -> OptKey {
                       const VoltMod::Pawn caller = ctx.Caller().Pawn();
                       if (!caller)
                       {
                           return std::nullopt;
                       }
                       ctx.Target().Pawn().Teleport(ClearedDestination(caller), std::nullopt, Vector{0.0f, 0.0f, 0.0f});
                       return "broadcast.brought";
                   }};

const Action Goto{Permission::Control, /*requireAlive*/ true, [](const ActionContext& ctx) -> OptKey {
                      const VoltMod::Pawn caller = ctx.Caller().Pawn();
                      if (!caller)
                      {
                          return std::nullopt;
                      }
                      caller.Teleport(ClearedDestination(ctx.Target().Pawn()), std::nullopt, Vector{0.0f, 0.0f, 0.0f});
                      return "broadcast.goto";
                  }};

void Swap(App& app, VoltMod::PlayerRef admin, VoltMod::PlayerRef first, VoltMod::PlayerRef second)
{
    if (first == second)
    {
        return;
    }
    auto ctxA = app.Actions.Resolve(admin, first, Permission::Control);
    auto ctxB = app.Actions.Resolve(admin, second, Permission::Control);
    if (!ctxA || !ctxB)
    {
        return;
    }
    const VoltMod::Pawn a = ctxA->Target().Pawn();
    const VoltMod::Pawn b = ctxB->Target().Pawn();
    if (!a.IsAlive() || !b.IsAlive())
    {
        return;
    }

    // Both spots empty in the same frame, so the exact origins need no clearance.
    const Vector originA = a.Origin();
    const Vector originB = b.Origin();
    a.Teleport(originB, std::nullopt, Vector{0.0f, 0.0f, 0.0f});
    b.Teleport(originA, std::nullopt, Vector{0.0f, 0.0f, 0.0f});
    BroadcastPair(app, *ctxA, *ctxB, "broadcast.swapped");
}

}  // namespace AdminSystem::Admin::Actions
