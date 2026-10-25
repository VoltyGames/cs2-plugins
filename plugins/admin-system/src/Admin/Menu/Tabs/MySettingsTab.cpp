#include "Admin/Menu/Tabs/MySettingsTab.hpp"

#include "Admin/AdminManager.hpp"
#include "Admin/Effects/Descriptors.hpp"
#include "Admin/Menu/MenuAccess.hpp"
#include "Admin/Menu/MenuCatalog.hpp"
#include "App.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Menu/MenuBuilder.hpp>
#include <VoltMod/Menu/MenuPresets.hpp>
#include <VoltMod/Messaging/ChatColors.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace AdminSystem::Admin::Menu
{

using VoltMod::ChoiceRow;
using VoltMod::MenuBuilder;
using VoltMod::ToggleRow;

namespace ChatColors = VoltMod::ChatColors;

// Explicit keys keep compound color names stable across palette changes.
static const std::unordered_map<std::string_view, std::string_view>& ColorLabelKeys()
{
    static const std::unordered_map<std::string_view, std::string_view> kKeys = {
        {"default", "color.default"}, {"darkred", "color.darkRed"},     {"lightpurple", "color.lightPurple"},
        {"green", "color.green"},     {"olive", "color.olive"},         {"lime", "color.lime"},
        {"red", "color.red"},         {"gray", "color.gray"},           {"yellow", "color.yellow"},
        {"silver", "color.silver"},   {"lightblue", "color.lightBlue"}, {"darkblue", "color.darkBlue"},
        {"purple", "color.purple"},   {"lightred", "color.lightRed"},   {"gold", "color.gold"},
    };
    return kKeys;
}

// Empty means inherit from the group and maps to choice index zero.
static int ToChoiceIndex(std::string_view color)
{
    if (color.empty())
    {
        return 0;
    }
    for (size_t i = 0; i < ChatColors::Palette.size(); ++i)
    {
        if (ChatColors::Palette[i].Name == color)
        {
            return static_cast<int>(i + 1);
        }
    }

    return 0;
}

static std::vector<VoltMod::Labeled<std::string>> BuildColorChoices(App& app, int viewerSlot)
{
    auto& translations = app.Runtime.Translations;
    const auto& keys = ColorLabelKeys();

    std::vector<VoltMod::Labeled<std::string>> choices;
    choices.reserve(ChatColors::Palette.size() + 1);

    // Group inheritance is distinct from the `default` color override.
    choices.push_back({.Label = translations.Get("color.groupDefault", viewerSlot), .Value = ""});

    // The framework renders the palette; colors without a translation key fall back to their name.
    auto palette = ChatColors::PaletteChoices([&](std::string_view name) -> std::string {
        if (auto it = keys.find(name); it != keys.end())
        {
            return translations.Get(it->second, viewerSlot);
        }
        return {};
    });
    choices.insert(choices.end(), std::make_move_iterator(palette.begin()), std::make_move_iterator(palette.end()));
    return choices;
}

enum class ColorSlot
{
    Name,
    Message,
};

// Read the stored override, not the resolved inherited color.
static std::string CurrentSlotColor(App& app, int64_t steamId, ColorSlot slot)
{
    const auto* admin = app.Admins.GetAdmin(steamId);
    if (!admin)
    {
        return "";
    }
    switch (slot)
    {
    case ColorSlot::Name:
        return admin->NameColor;
    case ColorSlot::Message:
        return admin->MessageColor;
    }
    return "";
}

/** Write one color back, leaving the admin's other chat settings as they are. */
static void SaveColor(App& app, int64_t steamId, ColorSlot slot, const std::string& value)
{
    auto& admins = app.Admins;
    const auto* admin = admins.GetAdmin(steamId);
    if (!admin)
    {
        return;
    }

    const std::string& name = slot == ColorSlot::Name ? value : admin->NameColor;
    const std::string& message = slot == ColorSlot::Message ? value : admin->MessageColor;
    admins.UpdateChatStyleAsync(steamId, admin->DisplayPrefix, name, message);
}

static VoltMod::MenuItem ColorRow(const MenuContext& ctx, const RowSpec& spec, ColorSlot slot,
                                  std::vector<VoltMod::Labeled<std::string>> choices)
{
    App& app = ctx.Plugin;
    const int64_t steamId = ctx.Admin.SteamId;

    return ChoiceRow<std::string>{
        .Label = ctx.Translate(spec.LabelKey),
        .Choices = std::move(choices),
        .Commit = [&app, steamId, slot](int, const std::string& value) { SaveColor(app, steamId, slot, value); },
        .Index = ToChoiceIndex(CurrentSlotColor(app, steamId, slot))}
        .ToItem();
}

/** Hide acts on the admin alone, which is why it sits here and not among the target rows. */
static VoltMod::MenuItem HideRow(const MenuContext& ctx, const RowSpec& spec)
{
    App& app = ctx.Plugin;
    const VoltMod::PlayerRef admin = ctx.Admin;

    return ToggleRow{
        .Label = ctx.Translate(spec.LabelKey),
        .Get = [&app, slot = admin.Slot](int) { return app.Effects.IsActive(slot, app.EffectDescriptors.Hide.Id); },
        .Flip = [&app, admin](int) { app.PlayerEffects.Toggle(admin, admin, app.EffectDescriptors.Hide); },
        .Enabled = Allows(app, spec.Permission)}
        .ToItem();
}

static VoltMod::MenuItem PrefixRow(const MenuContext& ctx, const RowSpec& spec)
{
    App& app = ctx.Plugin;
    const int64_t steamId = ctx.Admin.SteamId;

    return ToggleRow{.Label = ctx.Translate(spec.LabelKey),
                     .Get =
                         [&app, steamId](int) {
                             const auto* admin = app.Admins.GetAdmin(steamId);
                             return admin ? admin->DisplayPrefix : true;
                         },
                     .Flip =
                         [&app, steamId](int) {
                             const auto* admin = app.Admins.GetAdmin(steamId);
                             if (admin)
                             {
                                 app.Admins.UpdateChatStyleAsync(steamId, !admin->DisplayPrefix, admin->NameColor,
                                                                 admin->MessageColor);
                             }
                         }}
        .ToItem();
}

std::shared_ptr<VoltMod::Menu> BuildMySettingsTab(const MenuContext& ctx)
{
    MenuBuilder builder(ctx.Translate("category.mySettings"));

    // Both color rows offer the same palette, so it is translated once for the two of them.
    const std::vector<VoltMod::Labeled<std::string>> palette = BuildColorChoices(ctx.Plugin, ctx.Admin.Slot);

    // Every row here persists immediately; the menu has no Save action.
    AppendCatalogRows(ctx, builder, MySettingsRows, [&](const RowSpec& spec) -> VoltMod::MenuItem {
        switch (spec.Id)
        {
        case RowId::Hide:
            return HideRow(ctx, spec);
        case RowId::ChatPrefix:
            return PrefixRow(ctx, spec);
        case RowId::NameColor:
            return ColorRow(ctx, spec, ColorSlot::Name, palette);
        case RowId::MessageColor:
            return ColorRow(ctx, spec, ColorSlot::Message, palette);
        default:
            return {};
        }
    });

    return builder.Build();
}

}  // namespace AdminSystem::Admin::Menu
