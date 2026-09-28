#pragma once

#include "Admin/Access.hpp"
#include "Admin/Actions/ActionDispatcher.hpp"
#include "Admin/Actions/Descriptors.hpp"
#include "Admin/AdminManager.hpp"
#include "Admin/CheatCheck/CheatCheckManager.hpp"
#include "Admin/Effects/Descriptors.hpp"
#include "Admin/Effects/EffectDispatcher.hpp"
#include "Admin/Effects/EffectManager.hpp"
#include "Admin/FreezeManager.hpp"
#include "Admin/Menu/ActionRows.hpp"
#include "Config/ConfigManager.hpp"
#include "Core/AdminActionsService.hpp"
#include "Core/AdminMenuSection.hpp"
#include "Core/ChatService.hpp"
#include "Core/PermissionService.hpp"
#include "Core/PlayerChat.hpp"
#include "Database/Repositories.hpp"
#include "Fun/FunMode.hpp"
#include "Maps/MapCycleState.hpp"
#include "Maps/VoteState.hpp"
#include "Punishments/PunishmentManager.hpp"
#include "Reports/ReportFlow.hpp"
#include "Reports/ReportManager.hpp"
#include "Reports/ReportMenuSection.hpp"

#include <Ui/AdminMenu.hpp>
#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Signals/Subscription.hpp>
#include <VoltMod/Core/Signals/Subscriptions.hpp>
#include <VoltMod/Database/Api.hpp>
#include <VoltMod/Menu/PanoramaMenuLayout.hpp>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>

namespace AdminSystem
{

/** One load cycle's object graph. Members are declared in dependency order and destroyed in
 *  reverse. Permissions: ask Access, not Admins. Chat: PlayerChat handles input, ChatService only
 *  sends. */
struct App final : VoltMod::Plugin
{
    explicit App(VoltMod::Runtime& runtime) : Plugin(runtime) {}
    ~App() override;
    App(const App&) = delete;
    App& operator=(const App&) = delete;

    /** Connects the database, runs migrations, loads admins and registers commands. */
    bool Load() override;

    /** Opens the admin menu for @p slot; false when it could not be built. */
    bool OpenAdminMenu(int slot);

    /** Admin-panel rows for an admin/target pair. Build them here, not in each menu file. With no
     *  @p target the rows deny. */
    Admin::Menu::ActionRows MenuRows(VoltMod::PlayerRef admin, std::optional<VoltMod::PlayerRef> target = std::nullopt)
    {
        return Admin::Menu::ActionRows({.Actions = Actions,
                                        .Policy = Runtime.Policy,
                                        .Translations = Runtime.Translations,
                                        .Players = Runtime.Players,
                                        .Entities = Runtime.Entities,
                                        .Menus = Runtime.Menus,
                                        .PlayerEffects = PlayerEffects,
                                        .Effects = Effects},
                                       admin, std::move(target));
    }

    /** The admin menu layout, and the menu drawn on it when `menu.panorama` is on. */
    VoltMod::PanoramaMenuLayout MenuLayout{Runtime.Screens, AdminMenuLayout::Name, AdminMenuLayout::Tabs.size(),
                                           AdminMenuLayout::Rows.size(), AdminMenuLayout::IconSetNames};
    /** Declared after the layout, so it releases first. */
    VoltMod::Subscription Panorama;
    VoltMod::Subscription Addon;

    Config::ConfigManager Settings = VoltMod::LoadConfig<Config::ConfigManager>(Runtime);
    /** Runs actions through Runtime::Policy (permissions, targeting) and announces them. */
    Admin::Actions::ActionDispatcher Actions{Runtime.Policy};
    /** Actions that need Runtime beyond ActionContext (Slap, Smite). */
    Admin::Actions::ActionDescriptors ActionDescriptors{Runtime};
    VoltMod::Database Db{Runtime.Scheduler};
    Database::Repositories Repos{Db};
    Core::ChatService Chat{Runtime, Settings};
    /** Map list, queued next map, and the level change. */
    Maps::MapCycleState MapCycle{Runtime, Settings};
    Fun::FunMode FunMode{Runtime};
    Maps::VoteState Votes{Runtime, Settings, MapCycle};
    Admin::AdminManager Admins{Repos, Settings};
    Admin::FreezeManager Freeze{Repos, Settings, Runtime, Chat, Admins};
    /** Permissions minus freezes. Ask this, not Admins. */
    Admin::Access Access{Admins, Freeze};
    Punishments::PunishmentManager Punishments{Repos, Settings, Runtime, Chat};
    Core::PlayerChat PlayerChat{Runtime, Settings, Chat, Admins, Punishments};
    Reports::ReportManager Reports{Repos, Settings, Runtime};
    Reports::ReportFlow ReportMenu{Runtime, Settings, Reports};
    Admin::Effects::EffectManager Effects{Runtime.Scheduler};
    /** Runs effects through Actions. */
    Admin::Effects::EffectDispatcher PlayerEffects{Actions, Effects};
    Admin::Effects::EffectDescriptors EffectDescriptors{Runtime};
    Admin::CheatCheck::CheatCheckManager CheatCheck{Runtime, Settings, Chat, Punishments};
    /** Published in Load; each withdraws itself before what it wraps dies. */
    Core::AdminActionsService AdminActions{Runtime, Punishments, Access};
    Core::PermissionService SharedPermissions{Runtime, Access};
    Core::AdminMenuSection AdminSection{Runtime, Admins, [this](int slot) { return OpenAdminMenu(slot); }};
    Reports::ReportMenuSection ReportSection{Runtime, Settings, Reports, ReportMenu};
    /** Migration result, shown by `admin_status`. */
    VoltMod::MigrationResult Migration;

private:
    void InstallPolicy();
    void RegisterPlayerLifecycle();
    /** Home page text: greeting, players online, map. */
    void AddHomePageText();
    /** Keeps a banned account out; it sees the ban reason. */
    void RefuseBanned(VoltMod::ConnectRequest& request);
    void OnPlayerConnect(VoltMod::Player& player);
    void OnPlayerDisconnect(VoltMod::Player& player);
    VoltMod::Status ConnectDatabase();
    VoltMod::Status LoadAdminData();
    VoltMod::Status InitializePunishments();
    void RegisterGameEventListeners();
    /** A voice-muted sender is heard by nobody. */
    void RegisterVoiceMuteHook();
    void InstallStatusReporting();
    void RegisterCommands();

    /** Declared last so handlers stop before the state they capture. */
    VoltMod::Subscriptions _subs;
};

}  // namespace AdminSystem
