#include "App.hpp"

#include "Admin/Effects/Model.hpp"
#include "Admin/Menu/MenuAccess.hpp"
#include "Admin/Menu/RootMenu.hpp"
#include "Commands/Commands.hpp"
#include "Config/ConfigManager.hpp"

#include <VoltMod/Api.hpp>
#include <VoltMod/Database/Api.hpp>
#include <VoltMod/Events/EventTypes.hpp>
#include <VoltMod/Unsafe/Hook.hpp>
#include <algorithm>
#include <string>
#include <utility>

using VoltMod::Error;
using VoltMod::Player;
using VoltMod::Status;
namespace Log = VoltMod::Log;

namespace AdminSystem
{

/** Keeps a voice-muted sender from being heard: the engine runs with listening off. */
static VoltMod::HookResult<bool> SilenceMuted(VoltMod::PlayerManager& players,
                                             const Punishments::PunishmentManager& punishments,
                                             Core::PlayerChat& chat, IVEngineServer2& engine, CPlayerSlot receiver,
                                             CPlayerSlot sender, bool listen)
{
    if (!listen)
    {
        return {};
    }
    VoltMod::Player* muted = players.Get(sender.Get());
    if (!muted || !punishments.IsPunished(Punishments::PunishType::VoiceMute, muted->SteamId()))
    {
        return {};
    }

    // Called once per receiver; ChatService collapses it to one chat line.
    chat.NotifyVoiceMuted(muted);
    VoltMod::CallOriginal(&IVEngineServer2::SetClientListening, &engine, receiver, sender, false);
    return VoltMod::HookResult<bool>::Block(false);
}

static VoltMod::Subscription HookVoiceMute(IVEngineServer2* engine, VoltMod::PlayerManager& players,
                                           const Punishments::PunishmentManager& punishments, Core::PlayerChat& chat)
{
    const auto onSetClientListening = [&players, &punishments, &chat](IVEngineServer2& engine, CPlayerSlot receiver,
                                                                      CPlayerSlot sender, bool listen) {
        return SilenceMuted(players, punishments, chat, engine, receiver, sender, listen);
    };
    return VoltMod::HookInterface(&IVEngineServer2::SetClientListening, engine, onSetClientListening);
}

App::~App()
{
    CheatCheck.CancelAll();
    Effects.CancelAll();
    // Record every session still open, as a disconnect would, while the database is up.
    for (Player* player : Runtime.Players.All())
    {
        OnPlayerDisconnect(*player);
    }
    Db.Disconnect();
}

void App::InstallPolicy()
{
    auto& policy = Runtime.Policy;
    // CanTarget stays unset: only punishments check rank, where they are issued.
    policy.Reply = [this](int slot, std::string_view message) { Chat.Reply(slot, message); };
    Actions.OnBroadcast = [this](const VoltMod::Authorized& who, std::string_view key) {
        // No target and self-target both read "Bob noclipped".
        const bool named = who.Target && who.Target != &who.Caller;
        Chat.BroadcastAction(key, who.Caller.Name(), named ? who.Target->Name() : std::string_view{});
    };
}

void App::RegisterPlayerLifecycle()
{
    _subs.Add(Runtime.Players.Connecting += [this](VoltMod::ConnectRequest& request) { RefuseBanned(request); });
    _subs.Add(Runtime.Players.Connected += [this](Player& player) { OnPlayerConnect(player); });
    _subs.Add(Runtime.Players.Disconnected += [this](Player& player) { OnPlayerDisconnect(player); });
}

void App::RefuseBanned(VoltMod::ConnectRequest& request)
{
    if (auto ban = Punishments.GetActive(AdminSystem::Punishments::PunishType::Ban, request.SteamId))
    {
        request.Rejected = true;
        request.Reason = ban->Reason;
    }
}

void App::OnPlayerConnect(Player& player)
{
    const int64_t steamId = player.SteamId();
    const int slot = player.Slot();
    Repos.Players.RecordConnectAsync(steamId, player.Name(), std::string(player.Ip()));

    // Tell a frozen admin now, not at their first denied command.
    if (Freeze.IsFrozen(steamId))
    {
        Freeze.NotifyFrozenSoon(slot, steamId);
    }
}

void App::OnPlayerDisconnect(Player& player)
{
    Repos.Players.RecordDisconnectAsync(player.SteamId(), player.Name(), player.Playtime().count());
    Effects.CancelAll(player.Slot());
    CheatCheck.CancelAllForSlot(player.Slot());
}

Status App::ConnectDatabase()
{
    if (!Db.Connect(Settings.Get().database))
    {
        return std::unexpected(Error::Engine("unavailable; chat commands will reject all callers"));
    }

    Migration = VoltMod::RunMigrations(Db, Runtime.PluginFile("migrations"),
                                       {.HistoryTable = "schema_migrations", .LockKey = 727274});
    if (!Migration)
    {
        return std::unexpected(Error::Failed("migrations failed; not loading admins against an out-of-date schema"));
    }

    const auto& server = Settings.Get().server;
    if (!Repos.Servers.Upsert(server.tag, server.name))
    {
        Log::Warn("Failed to register server '{}' in the servers table.", server.tag);
    }

    return {};
}

Status App::LoadAdminData()
{
    const bool groups = Admins.LoadGroups();
    const bool admins = Admins.LoadAdmins();
    Freeze.RefreshFromDatabase();
    if (!groups || !admins)
    {
        return std::unexpected(Error::Failed("failed to load groups/admins from DB"));
    }
    return {};
}

Status App::InitializePunishments()
{
    const bool loaded = Punishments.LoadActivePunishments();

    // Picks up freezes from other servers and keeps this server's registry entry alive.
    _subs.Add(Runtime.Scheduler.Repeat(60'000, [this] {
        Punishments.ExpireOldPunishments();
        Freeze.RefreshFromDatabase();
        Repos.Servers.HeartbeatAsync(Settings.Get().server.tag);
    }));

    // Only now: the database and admins are ready.
    AdminActions.Publish();
    SharedPermissions.Publish();

    if (!loaded)
    {
        return std::unexpected(Error::Failed("failed to load active punishments"));
    }
    return {};
}

void App::RegisterGameEventListeners()
{
    auto& events = Runtime.GameEvents;
    _subs.Add(events.On<VoltMod::PlayerDeath>([this](const VoltMod::PlayerDeath& e) {
        // Per-life effects only; EffectScope::Session survives death.
        Effects.CancelOnDeath(e.Slot);
    }));
    _subs.Add(events.On<VoltMod::RoundEnd>([this](const VoltMod::RoundEnd&) {
        Effects.CancelRound();
        // After the round, so players see the scoreboard.
        MapCycle.ChangeToNext();
    }));
    _subs.Add(events.On<VoltMod::RoundPrestart>([this](const VoltMod::RoundPrestart&) { Effects.CancelRound(); }));
    _subs.Add(events.On<VoltMod::PlayerTeam>([this](const VoltMod::PlayerTeam& e) {
        // Hide is spectator-only; joining a team ends it.
        if (e.Disconnect)
        {
            return;
        }
        if (VoltMod::IsPlaying(e.Team))
        {
            Effects.Cancel(e.Slot, EffectDescriptors.Hide.Id);
        }
    }));
}

void App::InstallStatusReporting()
{
    auto& status = Runtime.Status;

    status.RegisterSection("db", [this] {
        return VoltMod::Json::Write(glz::obj{"connected", Db.IsConnected(), "driver",
                                             VoltMod::DriverName(Db.GetDriver()), "migrationVersion",
                                             Migration.CurrentVersion, "migrationsApplied", Migration.Applied});
    });

    status.RegisterSection("admins", [this] {
        return VoltMod::Json::Write(glz::obj{"cached", Admins.AdminCount(), "groups", Admins.GroupCount()});
    });

    status.RegisterSection("commands",
                           [this] { return VoltMod::Json::Write(glz::obj{"registered", Runtime.Commands.Count()}); });

    status.RegisterSection("server", [this] {
        const auto& server = Settings.Get().server;
        return VoltMod::Json::Write(glz::obj{"tag", server.tag, "name", server.name});
    });

    status.InstallCommand("admin_status",
                          "Report plugin health; 'admin_status json' emits a machine-readable STATUS_JSON line.",
                          [this] { return Db.IsConnected(); });
}

void App::RegisterCommands()
{
    auto& commands = Runtime.Commands;
    Commands::RegisterAdminMenuCommand(commands, *this);
    Commands::RegisterAdminSelfCommands(commands, *this);
    Commands::RegisterCheatCheckCommands(commands, *this);
    Commands::RegisterFreezeCommands(commands, *this);
    Commands::RegisterInfoCommands(commands, *this);
    Commands::RegisterPunishmentCommands(commands, *this);
    Commands::RegisterReportCommand(commands, *this);
}

bool App::OpenAdminMenu(int slot)
{
    auto menu = Admin::Menu::BuildRootMenu(*this, slot);
    if (!menu)
    {
        return false;
    }

    // The root shows the home page; its rows only repeat the sidebar.
    Runtime.Menus.OpenSession(slot, std::move(menu), {.HomePage = true});
    return true;
}

void App::AddHomePageText()
{
    auto translated = [this](std::string_view key) {
        return [this, key](int slot) { return Runtime.Translations.Get(key, slot); };
    };
    MenuLayout.AddText(AdminMenuLayout::HomeTitleVar, [this](int slot) {
        const Player* player = Runtime.Players.Get(slot);
        return Runtime.Translations.Get("home.title", slot, {{"name", player ? player->Name() : std::string{}}});
    });
    MenuLayout.AddText(AdminMenuLayout::HomeBodyVar, translated("home.body"));
    MenuLayout.AddText(AdminMenuLayout::HomePlayersLabelVar, translated("home.players"));
    MenuLayout.AddText(AdminMenuLayout::HomePlayersVar, [this](int) {
        return std::to_string(
            std::ranges::count_if(Runtime.Players.All(), [](const Player* p) { return !p->IsBot(); }));
    });
    MenuLayout.AddText(AdminMenuLayout::HomeMapLabelVar, translated("home.map"));
    MenuLayout.AddText(AdminMenuLayout::HomeMapVar, [this](int) { return Runtime.Map.Current(); });
}

bool App::Load()
{
    Admin::Menu::VerifyCatalog(*this);
    InstallPolicy();
    RegisterPlayerLifecycle();
    Addon = Runtime.AddonManager.Add(Settings.Get().addonId);
    if (Settings.Get().menu.panorama)
    {
        AddHomePageText();
        Panorama = Runtime.UsePanorama(MenuLayout);
    }

    // No database: skip the steps that need it.
    auto& report = Runtime.LoadReport;
    const bool database = report.Optional("Database", ConnectDatabase());
    if (database)
    {
        report.Optional("Admins", LoadAdminData());
    }

    RegisterCommands();
    AdminSection.Publish();
    ReportSection.Publish();

    if (database)
    {
        report.Optional("Punishments", InitializePunishments());
    }

    RegisterGameEventListeners();
    _subs.Add(HookVoiceMute(Runtime.Unsafe.Interfaces.Engine, Runtime.Players, Punishments, PlayerChat));
    // Takes effect on the next map load.
    Admin::Effects::PrecacheModels(Runtime);
    // Reports bad map names now, not at the first !map.
    MapCycle.VerifyAgainstEngine();

    InstallStatusReporting();
    return true;
}

}  // namespace AdminSystem
