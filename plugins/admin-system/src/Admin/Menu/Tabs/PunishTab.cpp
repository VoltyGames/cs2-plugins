#include "Admin/Menu/Tabs/PunishTab.hpp"

#include "Admin/Menu/Flows/LiftFlow.hpp"
#include "Admin/Menu/Flows/PunishFlow.hpp"
#include "Admin/Menu/MenuAccess.hpp"
#include "Admin/Menu/MenuCatalog.hpp"
#include "Admin/Menu/Pickers/PlayerPicker.hpp"
#include "App.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Menu/MenuBuilder.hpp>
#include <VoltMod/Runtime.hpp>

using AdminSystem::Punishments::PunishType;

namespace AdminSystem::Admin::Menu
{

using VoltMod::ButtonRow;
using VoltMod::MenuBuilder;
using VoltMod::SubmenuRow;

/** The punishment a catalog row issues. */
static PunishType ToPunishType(RowId id)
{
    switch (id)
    {
    case RowId::PunishBan:
        return PunishType::Ban;
    case RowId::PunishVoiceMute:
        return PunishType::VoiceMute;
    case RowId::PunishTextMute:
        return PunishType::TextMute;
    case RowId::PunishWarn:
        return PunishType::Warn;
    default:
        return PunishType::Kick;
    }
}

std::shared_ptr<VoltMod::Menu> BuildPunishTab(const MenuContext& ctx)
{
    MenuBuilder builder(ctx.Translate("category.punish"));

    if (ctx.Visible(PunishLiftList))
    {
        builder.Add(SubmenuRow{.Label = ctx.Translate(PunishLiftList.LabelKey),
                               .Build = [ctx](int) { return BuildLiftMenu(ctx); }});
    }

    AppendTargetRows(ctx, builder, [ctx](VoltMod::PlayerRef target) { return BuildPunishCard(ctx, target); });

    return builder.Build();
}

std::shared_ptr<VoltMod::Menu> BuildPunishCard(const MenuContext& ctx, VoltMod::PlayerRef targetRef)
{
    App& app = ctx.Plugin;
    const int adminSlot = ctx.Admin.Slot;

    const auto title = ctx.CardTitle("category.punish", targetRef);
    if (!title)
    {
        return nullptr;
    }

    MenuBuilder builder(*title);

    if (AnyTemplateUsable(app, adminSlot, targetRef))
    {
        builder.Submenu(ctx.Translate("punish.quickPunish"),
                        [&app, targetRef](int slot) { return BuildQuickPunishMenu(app, slot, targetRef); });
    }

    AppendCatalogRows(ctx, builder, PunishCardRows, [&](const RowSpec& spec) -> VoltMod::MenuItem {
        const PunishType type = ToPunishType(spec.Id);
        return ButtonRow{
            .Label = ctx.Translate(spec.LabelKey),
            .Activate = [&app, pending = PendingPunishment{.Type = type, .Target = targetRef}](
                            int slot) { StartPunishFlow(app, slot, pending); },
            .Enabled = [&app, targetRef, type](int slot) { return CanStillPunish(app, slot, targetRef, type); }}
            .ToItem();
    });

    return builder.Build();
}

}  // namespace AdminSystem::Admin::Menu
