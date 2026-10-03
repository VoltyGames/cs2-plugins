---
paths:
  - "plugins/**"
  - "contracts/**"
---

# Framework patterns

## Lifecycle

The plugin is a DLL the VoltMod host loads. A plugin's engine events arrive in load order, and a
console command one plugin consumes is not offered to the next.

- `plugin.json` beside the plugin's `CMakeLists.txt` is its identity: name, version, log tag, description, dependencies. Nothing in C++ or CMake repeats it; read `runtime.PluginName` and `runtime.Version`.
- `src/App.hpp` declares `<Namespace>::App`, derived from `VoltMod::Plugin` with `using Plugin::Plugin;`. `voltmod_add_plugin` generates the entry point from it; there is no macro. Override `bool Load()` only for work that can fail the load or acts outside the plugin.
- Map starts and chat are events: `runtime.Map.Started`, and `runtime.Players.Said` for a line no menu or command took (set `Blocked` to keep it out of chat). There are no lifecycle virtuals.
- The `App` lives for one load cycle. Nothing may survive `volt reload`.
- `ConfigManager Config = VoltMod::LoadConfig<ConfigManager>(Runtime);` as the App's first member loads settings and translations, so every member below is built with them; a failure refuses the plugin before `Load`. `runtime.PluginFile("data/x")` builds any other path under the plugin's directory: `configs/` for files the operator tunes (seeded once), `data/` for files the plugin ships.

## Commands

Register from `App::Load()` with the fluent builder:

```cpp
commands.Add("slap")
    .Describe("Slap a player")
    .Permission(Permission::Slap)
    .Run([&app](Caller c, Args::Target target, Args::Rest reason) { ... });
```

- The handler's parameter list is the argument spec: `Caller` first, then one `Args::` value per argument. Targets, durations, and reasons arrive parsed and immunity-checked.
- A handler returns `c.Ok`/`c.Fail`, or nothing when it has nothing to say. Only one that mixes both returns `Reply::Silent()` and declares `-> Result<Reply>`.
- Read arguments through them: `target->Name()`, `why.ValueOr(fallback)`. `c.Translations.Get(key)` with no slot is the server language, for reasons stored or announced.
- `CommandManager` owns commands for the load cycle. Event, timer, and hook subscriptions live in the App's `_subs`.

## Authorization

- Gate with `.Permission("x")` in any plugin: the runtime asks admin-system's published `VoltMod::IPermissions`, and denies while it is not loaded. admin-system publishes it and alone sets `Policy.Reply` and its dispatcher's `OnBroadcast`.
- Ask `Policy::Authorize(caller, target, permission)` wherever the answer is needed. Never re-implement the check.
- A plugin's `CanTarget` is an immunity comparison only; console and self-targeting are settled before it runs.

## Players

- Store a `PlayerRef` (slot + SteamID) and resolve it with `runtime.Players.Get(ref)` where used.
- Handle connect and disconnect by subscribing to `runtime.Players.Connected`, `.FullyConnected`, `.SettingsChanged`, `.Disconnected`. There are no lifecycle virtuals.

## Subscriptions and hooks

- Subscribe with `+=` on `Event` members (`runtime.Slots.Changed`, `runtime.Movement.Before`, ...) and with `runtime.GameEvents.On<T>()` for game events. Every game event has a generated struct in `Events/EventTypes.hpp` (`player_death` is `PlayerDeath`, `dmg_health` is `DmgHealth`); there is no string form. The player an event is about is `e.Slot`, always valid, so don't guard it; other players are `<Key>Slot` and may be -1.
- Every subscription returns a `Subscription`. Keep it in a `Subscriptions` beside the state its handler captures: `_subs.Add(event += handler)`.
- A class subscribes and registers its commands in its constructor, unconditionally; settings are already loaded when it is built. VoltMod constructs the App after the runtime is ready and calls `Load` in the same step, so nothing fires in between. Work that can fail the load, or acts outside the plugin (a server convar, a published service), stays in `Load` or a method `Load` calls, because a broken settings file refuses the plugin only after every member is built.
- Construct per-slot state with the slot feed: `VoltMod::PerSlot<State> _state{runtime.Slots};`.
- Dropping a subscription unsubscribes, and cancels a `Scheduler` timer, so a fire-and-forget deferral still needs an owner.
- Hook services arm on the first subscription and disarm on the last. There is no `Install()`/`Enable()`. A leaked subscription leaves a live vtable hook after reload, and the host logs it by name when the plugin unloads.
- Name each hook handler in a local and pass it by name, so the hook call stays one line. Longer logic goes in a `static` function at the top of the .cpp, or a private member when it needs class state. The hook install goes in a `static` function, or a private `Install()` when it checks prerequisites or keeps the hook in class state.
- For an engine function the framework does not cover: `HookInterface`, `HookVirtual` or `HookFunction` from `<VoltMod/Unsafe/Hook.hpp>`, keeping the `Subscription` it returns. A handler is a lambda taking the hooked object first; a before-handler returns `HookResult` or nothing, an after-handler observes.

## Entities

- `Pawn` is the body (health, armor, movement, aim, weapons); `Controller` is the identity (name, money, team). Get them from `runtime.Entities.Pawn(slot)` and `.Controller(slot)`, or `player.Pawn()` and `player.Controller()`.
- All are frame-local. Store an `EntityRef` or `PlayerRef` and get it again where used: `runtime.Entities.Get(ref).Remove()`, or `runtime.Entities.Pawn(ref)` for a player pawn. `explicit operator bool()` is the only validity check, and a falsy wrapper ignores verbs, so `runtime.Entities.Pawn(slot).IsAlive()` needs no null check.
- Verbs live on the entity they act on: `entity.AcceptInput`, `Remove`, `RemoveAfter`, `SetModel`, `SetRender`, `EmitSound`; `pawn.GiveItem`, `SetVelocity`, `Heal`, `SetGodmode`, `SetMoveType`; `controller.ChangeTeam`, `Kick`, `ExecuteCommand`. Create through `runtime.Entities` (`Spawn`, `SpawnProp`, `SpawnParticle`, `SpawnLine`, `SpawnBeam`); walk with `Find` and `FindAll`. Never pass `.Raw()` to a framework call.
- Teams are `VoltMod::Team` with `IsPlaying` and `Opposite`; render colours are `VoltMod::Color{r, g, b[, a]}`. Handle fields end in `Ref` and return an `EntityRef`.
- Schema fields are generated pairs: `pawn.Health()` reads, `pawn.SetHealth(100)` writes and replicates. Offsets are baked by `voltmod framework schemagen`; the load aborts if they no longer match the engine.
- `runtime.Screens.Shared(layout)` and `runtime.Screens.ForPlayer(layout, slot)` return a move-only `Screen` whose destructor removes the entity; hold it as a member. `VoltMod::PlayerScreens` keeps one player screen per slot, created on first draw. `runtime.AddonManager.Add(Config.Get().addonId)` returns a `Subscription`; the requirement lasts as long as you hold it, and id 0 requires nothing. `IsReady(slot)` says whether a player has every addon any plugin requires.

## Errors and messages

- Return `Result<T>`/`Status` when the caller needs to know why. `Error::Detail` is log text, `Error::Key` the translation key for the player reply.
- All player-facing text goes through `Runtime::Messages` with translation keys: `SendKey(slot, key, tokens, kind)` for one player, `BroadcastKey` for everyone, each in their own language. `Send`/`Broadcast` take finished text.

## Menus and effects

- `MenuBuilder(title).Add(ButtonRow{...})` for rows, admin-system's `Admin::Menu::ActionRows` for rows acting on an admin/target pair, `Flow<TState>::Create(menus, slot, state)` for multi-step actions.
- Menus go through `runtime.Menus`: `OpenSession(slot, menu)` begins a session, `Open(slot, menu)` pushes onto it. With Panorama on, a plugin holds `runtime.UsePanorama(layout)`'s `Subscription` below its `VoltMod::PanoramaMenuLayout`; a player who is not `AddonManager.IsReady` gets center HTML.
- A Panorama menu screen is the framework's `menu` block (it draws the root panel too), styled by `menu_styles(ICONS)` from main-menu's `meatgg/menu_screen.css.j2`; don't restyle it per plugin.
- A plugin adds a main menu entry by publishing `Contracts::IMenuSection` with `Exchange.Publish<Contracts::IMenuSection>(impl, id)` and keeping the returned `Subscription` as the publisher's last member; main-menu's config names the id.
- Admin actions and effects are admin-system's own types (`Admin/Actions/`, `Admin/Effects/`): effects are `EffectDescriptor` values, and menu order comes from the explicit `MenuEffects` table.

## Configuration

- A settings struct is a plain aggregate at namespace scope. The member name is the JSON key, a missing key keeps the initializer, unknown keys are ignored.
- `VoltMod::Options<Settings>` loads the struct from `configs/settings.jsonc` and republishes it on every `Load`; `Reload()` reads the same file again. bhop and anticheat use it as their `ConfigManager` directly.
- When settings need validation or derived values, give `Options` a snapshot type and the function that builds it (`Options<Settings, ConfigSnapshot>{&BuildSnapshot}`), and wrap it in a plugin `ConfigManager` that offers `Get()` plus the derived values (admin-system `Config/ConfigManager.*`); read a section as `config.Get().chat`, not through a getter per section. The builder runs on a local copy and the snapshot is published in one move, so a failed reload leaves the previous one intact. Never publish a half-validated value.
- Resolve `VoltMod::ConVar<T>` handles once at start, not by name per call.
- Ask the service's `Available()` (`runtime.Movement`, `runtime.Screens`, ...) before relying on anything that depends on gamedata.

## Database

- `VoltMod::Database::RunAsync`/`Run` take a job callable over `auto& conn`, dispatched to whichever backend (Postgres, MariaDB, SQLite) is configured. A bare name blocks and is load-time only; `Async` returns first. Both report failure as `Result<T>` over `Error`.
- `VoltMod::Insert` returns the generated id; `VoltMod::Upsert` is the portable update-then-insert. Repository methods that return before the write lands end in `Async`.
- A migration is one dialect-free `migrations/NNNN_name.sql`; `RunMigrations` substitutes `@ID@`, `@NOW@`, `@TRUE@`, `@FALSE@`, `@INSERT_IF_ABSENT@` and `@ON_CONFLICT(cols)@` for the live driver. Add a change as a new numbered file; never edit one that has been applied.
- Table specs are generated from those migrations by `uv run poe schema` into `src/Database/Tables/Schema.hpp`; `poe lint` fails if they drift. Never edit the generated header.
- Managers take `Database::Repositories&`, built once in `App`. Do not construct a repository at a call site.
- admin-system settings: `configs/settings.jsonc`; migrations: `migrations/`. Several servers may share one database and `server.tag` identifies each. Run `!admin_reload` after editing admin data by hand.
