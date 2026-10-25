#include "Admin/Menu/MenuAccess.hpp"

#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Entities/EntitySystem.hpp>
#include <VoltMod/Entities/Pawn.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <algorithm>
#include <memory>
#include <utility>

namespace AdminSystem::Admin::Menu
{

bool Visible(App& app, int adminSlot, const RowSpec& row)
{
    if (!row.Children.empty())
    {
        return AnyVisible(app, adminSlot, row.Children);
    }
    if (row.Permission.empty())
    {
        return app.Admins.IsAdmin(app.Runtime.Players.GetRef(adminSlot).SteamId);
    }
    return MayUse(app, adminSlot, row.Permission);
}

bool AnyVisible(App& app, int adminSlot, std::span<const RowSpec> rows)
{
    return std::ranges::any_of(rows, [&](const RowSpec& row) { return Visible(app, adminSlot, row); });
}

VoltMod::MenuItem DisableUnless(VoltMod::MenuItem item, std::function<bool(int)> usable, std::string reason)
{
    auto describe = std::move(item.Describe);
    auto activate = std::move(item.Activate);
    auto step = std::move(item.Step);
    auto commit = std::move(item.Commit);

    // Shared, so the four wrappers below hold one predicate between them rather than a copy each.
    auto allowed = std::make_shared<std::function<bool(int)>>(std::move(usable));

    item.Describe = [describe = std::move(describe), allowed, reason = std::move(reason)](int slot) {
        VoltMod::MenuRow row = describe ? describe(slot) : VoltMod::MenuRow{};
        if (!row.Enabled || (*allowed)(slot))
        {
            return row;
        }
        row.Enabled = false;
        row.Value = reason;
        return row;
    };
    item.Activate = [activate = std::move(activate), allowed](int slot, VoltMod::MenuSurface& surface) {
        if (activate && (*allowed)(slot))
        {
            activate(slot, surface);
        }
    };
    item.Step = [step = std::move(step), allowed](int slot, int direction) {
        return step && (*allowed)(slot) && step(slot, direction);
    };
    item.Commit = [commit = std::move(commit), allowed](int slot) {
        if (commit && (*allowed)(slot))
        {
            commit(slot);
        }
    };
    return item;
}

VoltMod::MenuItem WhileAlive(App& app, int adminSlot, VoltMod::PlayerRef target, VoltMod::MenuItem item)
{
    auto alive = [&entities = app.Runtime.Entities, target](int) { return entities.Pawn(target.Slot).IsAlive(); };
    return DisableUnless(std::move(item), alive, app.Runtime.Translations.Get("hint.targetDead", adminSlot));
}

}  // namespace AdminSystem::Admin::Menu
