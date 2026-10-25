#include "Admin/Menu/Tabs/RoundModesTab.hpp"

#include "Admin/Menu/MenuAccess.hpp"
#include "Admin/Menu/MenuCatalog.hpp"
#include "App.hpp"
#include "Core/ChatService.hpp"
#include "Fun/FunMode.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Menu/MenuBuilder.hpp>
#include <VoltMod/Runtime.hpp>
#include <string>
#include <string_view>

namespace AdminSystem::Admin::Menu
{

using VoltMod::ButtonRow;
using VoltMod::MenuBuilder;
using VoltMod::ToggleRow;

std::shared_ptr<VoltMod::Menu> BuildRoundModesTab(const MenuContext& ctx)
{
    App& app = ctx.Plugin;
    const TabSpec& tab = FindTab(TabId::RoundModes);
    const VoltMod::EnabledCondition allowed = Allows(app, tab.Permission);

    MenuBuilder builder(ctx.Translate(tab.LabelKey));

    for (const auto& info : Fun::Toggles)
    {
        builder.Add(ToggleRow{.Label = ctx.Translate(info.NameKey),
                              .Get = [&app, id = info.Id](int) { return app.FunMode.IsOn(id); },
                              .Flip =
                                  [&app, id = info.Id, onKey = info.OnKey, offKey = info.OffKey](int slot) {
                                      app.Chat.BroadcastAction(app.FunMode.Flip(id) ? onKey : offKey,
                                                               Core::ActorName(app.Runtime, slot), std::string_view{});
                                  },
                              .Enabled = allowed});
    }

    builder.Add(ButtonRow{.Label = ctx.Translate("fun.clearAll"),
                          .Activate =
                              [&app](int slot) {
                                  app.FunMode.ClearAll();
                                  app.Chat.BroadcastAction("broadcast.funCleared", Core::ActorName(app.Runtime, slot),
                                                           std::string_view{});
                              },
                          .Enabled = allowed});

    return builder.Build();
}

}  // namespace AdminSystem::Admin::Menu
