#include "Admin/Menu/Flows/PunishFlow.hpp"

#include "Admin/AdminManager.hpp"
#include "Admin/Menu/Labels.hpp"
#include "App.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/ChatService.hpp"
#include "Punishments/IssuePunishment.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Text/Labeled.hpp>
#include <VoltMod/Core/Text/Strings.hpp>
#include <VoltMod/Core/Text/Translations.hpp>
#include <VoltMod/Menu/Flow.hpp>
#include <VoltMod/Menu/MenuBuilder.hpp>
#include <VoltMod/Players/PlayerManager.hpp>
#include <VoltMod/Runtime.hpp>
#include <format>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using AdminSystem::Punishments::IssuePunishment;
using AdminSystem::Punishments::LookUp;
using AdminSystem::Punishments::PunishType;

namespace AdminSystem::Admin::Menu
{

using VoltMod::Labeled;
using VoltMod::MenuBuilder;
using VoltMod::Strings;
using PunishFlowT = VoltMod::Flow<PendingPunishment>;

/** @p target is the reference the flow stored, so a target who left is refused rather than
 *  retargeted; the admin slot is the presser's, live at the moment this runs. */
bool CanStillPunish(App& app, int adminSlot, VoltMod::PlayerRef target, PunishType type)
{
    auto& players = app.Runtime.Players;
    const VoltMod::PlayerRef admin = players.GetRef(adminSlot);
    if (!app.Runtime.Policy.Authorize(admin, target, LookUp(type).RequiredPermission).has_value())
    {
        return false;
    }

    return app.Access.CanPunish(admin.SteamId, target.SteamId);
}

/** Re-checked at every step: the target may have left, the slot may rehost another player, and
 *  the admin's permission or immunity may have changed since the menu opened. */
static std::optional<std::string> ValidatePending(App& app, int slot, const PendingPunishment& pending)
{
    if (!app.Runtime.Players.Get(pending.Target))
    {
        return "punish.targetLost";
    }
    if (!CanStillPunish(app, slot, pending.Target, pending.Type))
    {
        return "punish.notAllowed";
    }
    return std::nullopt;
}

static void Issue(App& app, int adminSlot, PendingPunishment& pending)
{
    auto& translations = app.Runtime.Translations;
    auto* admin = app.Runtime.Players.Get(adminSlot);
    auto* target = app.Runtime.Players.Get(pending.Target);
    if (!admin || !target)
    {
        return;
    }

    // Captured before issuing: bans and kicks can drop the target immediately.
    const std::string targetName = target->Name();
    IssuePunishment(app, *admin, *target, pending.Type, pending.Reason, pending.DurationSec);

    // With broadcasts on, the admin already sees the server-wide line; avoid double messaging.
    if (!app.Settings.Get().chat.broadcastPunishments)
    {
        app.Chat.Reply(adminSlot,
                       translations.Get("punish.issued", adminSlot,
                                        {{"action", translations.Get(ActionTranslationKey(pending.Type), adminSlot)},
                                         {"name", targetName}}));
    }
}

/** The validated confirm -> issue tail every punish path shares, for the one admin @p adminSlot. */
static PunishFlowT::Ptr MakeBaseFlow(App& app, int adminSlot, PendingPunishment pending)
{
    auto& translations = app.Runtime.Translations;
    auto type = pending.Type;
    return PunishFlowT::Create(app.Runtime.Menus, adminSlot, std::move(pending))
        ->Validate([&app, adminSlot](const PendingPunishment& p) { return ValidatePending(app, adminSlot, p); })
        ->Confirm({.Title = ConfirmTitle(translations, ActionTranslationKey(type), adminSlot),
                   .Summary =
                       [&app, adminSlot](const PendingPunishment& p, VoltMod::SummaryRows& rows) {
                           auto& translations = app.Runtime.Translations;
                           auto* target = app.Runtime.Players.Get(p.Target);
                           rows.Add(translations.Get("punish.target", adminSlot),
                                    target ? target->Name() : std::string())
                               .AddIf(LookUp(p.Type).Timed, translations.Get("punish.duration", adminSlot),
                                      DurationLabel(translations, p.DurationSec, adminSlot))
                               .Add(translations.Get("punish.reason", adminSlot), Strings::TruncateUtf8(p.Reason, 40));
                       }})
        ->Finish([&app, adminSlot](PendingPunishment& p) { Issue(app, adminSlot, p); });
}

void StartPunishFlow(AdminSystem::App& app, int adminSlot, PendingPunishment pending)
{
    auto& translations = app.Runtime.Translations;
    auto type = pending.Type;
    // The flow runs for one admin, so every step string resolves in their language here.
    auto stepTitle = [&translations, type, adminSlot](std::string_view suffixKey) {
        return std::format("{}: {}", translations.Get(ActionTranslationKey(type), adminSlot),
                           translations.Get(suffixKey, adminSlot));
    };

    std::vector<Labeled<int>> durations;
    for (int seconds : app.Settings.GetMenuDurations())
    {
        durations.push_back({.Label = DurationLabel(translations, seconds, adminSlot), .Value = seconds});
    }

    std::vector<Labeled<std::string>> reasons;
    for (const auto& reason : app.Settings.Get().punishments.reasonPresets)
    {
        reasons.push_back({.Label = reason, .Value = reason});
    }

    MakeBaseFlow(app, adminSlot, std::move(pending))
        ->AddDurationStep({.Title = stepTitle("panel.selectDuration"),
                           .Presets = std::move(durations),
                           .Set = [](PendingPunishment& p, int seconds) { p.DurationSec = seconds; },
                           .CustomLabel = translations.Get("duration.custom", adminSlot),
                           .CustomPrompt = translations.Get("duration.customPrompt", adminSlot),
                           .Applies = [](const PendingPunishment& p) { return LookUp(p.Type).Timed; }})
        ->AddOptionsStep(
            {.Title = stepTitle("punish.selectReason"),
             .Options = std::move(reasons),
             .Set = [](PendingPunishment& p, const std::string& label, const std::string&) { p.Reason = label; },
             .CustomLabel = translations.Get("punish.customReason", adminSlot),
             .CustomPrompt = translations.Get("punish.customReasonPrompt", adminSlot)})
        ->Begin();
}

bool AnyTemplateUsable(AdminSystem::App& app, int adminSlot, VoltMod::PlayerRef target)
{
    for (const auto& tmpl : app.Settings.GetPunishmentTemplates())
    {
        if (CanStillPunish(app, adminSlot, target, tmpl.Type))
        {
            return true;
        }
    }
    return false;
}

std::shared_ptr<VoltMod::Menu> BuildQuickPunishMenu(AdminSystem::App& app, int adminSlot, VoltMod::PlayerRef target)
{
    auto& translations = app.Runtime.Translations;
    auto* targetPlayer = app.Runtime.Players.Get(target);
    if (!targetPlayer)
    {
        return nullptr;
    }

    MenuBuilder builder(std::format("{}: {}", translations.Get("punish.quickPunish", adminSlot), targetPlayer->Name()));

    builder.EmptyText(translations.Get("punish.noTemplates", adminSlot));

    for (const auto& tmpl : app.Settings.GetPunishmentTemplates())
    {
        if (!CanStillPunish(app, adminSlot, target, tmpl.Type))
        {
            continue;
        }

        PendingPunishment pending{
            .Type = tmpl.Type,
            .Target = target,
            .DurationSec = tmpl.DurationSec,
            .Reason = tmpl.Reason,
        };
        // Duration and reason are preset by the template, so the flow jumps straight to confirm.
        builder.Button(std::format("{} - {}", tmpl.Name, DurationLabel(translations, tmpl.DurationSec, adminSlot)),
                       [&app, pending](int slot) { MakeBaseFlow(app, slot, pending)->Begin(); });
    }

    // Permissions can change between the actions menu and here, so every template may filter out.
    return builder.Build();
}

}  // namespace AdminSystem::Admin::Menu
