# Stronghold redesign: structures, vehicles and weapons; APC and quad bike support; seat HUD; baked scale; new sounds

## Context

Stronghold grew one system at a time, and each new system copied the plumbing of the last. Three areas need a common shape.

**Structures.** There are ten kind systems in `src/Structures/`. Each one:
- runs its own timer;
- loops over `_structures.All()` with its own kind filter (written four different ways);
- keeps a map of state by structure id.

There is no event for a structure being built, moved, changing team or being removed. So six systems each poll `FindById` to purge their maps, and three different mechanisms detect a move.

`StructurePanel::Use` and `Target` are if-chains over kinds: rocket launcher, then vehicles, then stations. The panel takes 13 dependencies.

- Turret upgrades are gated by a kind check in `UpgradeDue`.
- Sabotage changes `Team` and `Owner` in place. It never re-skins a structure or re-hides a landmine from the new enemy team.
- **Bug:** if the free teleporter exit is sabotaged, removing it refunds the saboteur a share of the enemy's entrance.

**Vehicles.** `VehicleSeats`, `TankSystem`, `HelicopterSystem` and `DroneSystem` each walk all 64 slots every frame and filter by kind. Each also:
- keeps its own state map by structure id;
- has its own "moved while parked" reset.

There are also:
- two ways to put a rider out: the tank's `PutOut` and `HelicopterExit.cpp`;
- four `Scope()` builders, with key strings per vehicle and seat;
- hard-coded kind checks: `IsGunnerSeat`, `ScopeTextFor`, `Ka50` branches, `rodeInBody`, `IsDrone`, `Assets(ItemKind::Tank)`, and a `Part` enum;
- measured offsets spread over 4 files, all multiplied by a runtime scale (`TankScale`, `Scaled()`).

**Weapons.** A handheld launcher's behaviour is one `Homing` flag, and several things are wired to it:
- The Stinger's lock is wired in: the target rule, prompt keys and tones.
- `ProjectileSystem` has two sets of overloads, one for structures and one for launchers, that differ only in who is credited.
- The shop has two card builders and chooses between them by lookup order.
- Every weapon is a single-shot Zeus.
- Death, disconnect and round clean-up are wired by hand in `App.cpp`, and a team change never unloads the launcher.

A launcher that does anything beyond "straight" or "Stinger" touches about 10 C++ files.

**Goals:**
- One shape for each area: an interface or base class with plain hooks, per-kind data in the catalog, and one loop that drives them.
- Adding an APC, a quad bike, a new structure or a new weapon should mean new data plus one class, not edits across the code.
- Seats shown on the HUD, and a seat change with R.
- The scale baked into the models.
- CC0 sounds for the vehicles, and the unused sounds removed.
- Settings clean-up:
  - Drop `buildMs`. Nothing but the delay reads it (`BuiltAt`, `IsBuilt`, `IsWorking`), so structures work as soon as they are placed.
  - Add `features.helicopters` and `features.launchers` beside `features.tanks`.

**Decisions with the user:**
- R moves you to the next free seat.
- The scale is baked into the models: tank 0.8, helicopters 0.75.
- No seat lets a rider use their own weapon.
- The APC carries a driver, a gunner and 4 passengers; the quad bike has a driver only.

**Workflow:** see [Execution](#execution) at the end: a new branch, commits grouped by phase, and independent work handed to subagents.

**Constraints:**
- Riders are frozen standing pawns, 72 units tall.
- `configs/settings.jsonc` keys keep their names. The installer never overwrites a server's settings file, so a renamed key would silently fall back to its default.

**Naming:** C++ type and member names can't clash in `App`, so kind classes keep the `…System` suffix (`TurretSystem Turrets`). New types use plain words.

---

## Phase 1: Bake the scale into the models (tank 0.8, helicopters 0.75)

Scaling in the model makes model units equal game units. The mesh, hulls and animation then agree, every offset in code is the number you measure, and the ghost can't differ from the placed structure.

1. **Add a scale to the vmdl writer.**
   - `.claude/skills/3d-model/scripts/modelkit/modeldoc.py`: `write_vmdl(..., scale: float = 1.0)` adds a `ModelModifierList` holding a `ModelModifier_ScaleAndMirror` whenever the scale is not 1.
   - `SKILL.md` lines 119-121 and 193-195: say "resize with `write_vmdl(scale=…)`" instead of "the plugin's scale".
2. **Add the same modifier by hand** to these vmdls in `content/models/stronghold/`:
   - `tank/`: `tank`, `track_left`, `track_right`, `turret`, `gun` at 0.8. The `shell` stays at 1.
   - `ka50/`: `ka50`, `cannon` at 0.75.
   - `huey/`: `huey`, `door_gun` at 0.75.
3. **Compile and check.**
   - Run `uv run voltmod content compile stronghold models/stronghold/<model> --install client --install server`.
   - Check the hulls and the track and rotor animations in Source2Viewer, or with `ent_bbox`.
4. **Remove the runtime scale.**
   - Delete `StructureAssets::Scale`.
   - Drop the `PropSpec.Scale` uses in `StructureRegistry.cpp:68` and `Placement.cpp:176`.
   - Delete `TankScale`, `TankGunOnTurret`, `HelicopterScale`, `Scaled`, `ScaledBox`, `TankBox` and `Seat()`.
5. **Write offsets at final size.** Replace each offset with the model-space literal × 0.8 or × 0.75:
   - `Catalog.cpp`
   - `TankSystem.cpp`: `MuzzleReach`, `CameraAt`
   - `TankTracks.cpp`: `TrackSpeed`, `TrackOut`, `TrackPoints`

   Seat feet stay unscaled, because riders keep their size.
6. **Check head room in Blender.** A rider's head is at feet + 72.
   - The tank's turret roof is at 75.2, so the driver's feet go from 6 to about 2.
   - Measure the Ka-50 and Huey cabins at 0.75, and lower the feet where needed.
   - If a seat can't fit, raise that vehicle's scale instead.
7. **Update the docs.** Update the model rows in `docs/assets.md`. Rebuild the meatgg addon (`uv run poe meatgg-addon`) together with the server, so the server's hulls match the clients' models.

## Phase 2: Structures, one lifecycle and one loop

### Shape

```text
src/Building/
  Structure.hpp/.cpp          data record without BuiltAt; UpgradeDue reads item.upgrades, not the kind
  StructureRegistry.hpp/.cpp  storage and parts, now raising events; + ChangeTeam()
  StructureSystem.hpp         base class every kind system derives from, and struct Frame
  StructureDispatcher.hpp/.cpp runs each system on its interval, routes E and the card's action text
  PerStructure.hpp            state per structure: made on first use, reset on a move, dropped on removal
  StructurePanel.*, SabotageSystem.*, Placement/*, Damage/*   (kept, simplified)
src/Structures/<Group>/<Kind>System.*   each derives StructureSystem
```

### Registry events

`StructureRegistry` gets public `VoltMod::Event` members, following the framework's event pattern:

| Event | Raised from |
|---|---|
| `Built(Structure&)` | `Build` |
| `Moved(Structure&)` | `Move` |
| `TeamChanged(Structure&)` | `ChangeTeam` |
| `Removed(const Structure&)` | `RemovePending` and `RemoveAll`, just before each structure is deleted |

`ChangeTeam(Structure&, int ownerSlot)` moves the sabotage logic into the registry. It:
- sets owner and team;
- clears `Upgraders` and `Spent`;
- re-skins `TeamSkin` parts;
- redoes enemy hiding for `HiddenFromEnemies`;
- turns a teleporter's other half with it.

This also fixes the refund bug: both halves change owner together, and the exit costs 0.

### Base class

`Building/StructureSystem.hpp`:

```cpp
/** One frame as the dispatcher hands it to a system; Pawns() is listed once, on first use. */
struct Frame { Clock::time_point Now; float Seconds; std::span<const Pawns::LivePawn> Pawns(); };

/** The logic of one or more structure kinds. Registered with StructureDispatcher::Add, which calls it for its kinds. */
class StructureSystem
{
public:
    virtual ~StructureSystem() = default;
    virtual void Update(Structure& structure, Frame& frame) {}     // each of its structures, on its interval
    virtual void UpdateAll(Frame& frame) {}                          // once after, for work across them (tesla grenades, salvos)
    virtual std::string Action(int slot, const Structure&) { return {}; }   // the card's E line; empty = generic level-up
    virtual bool Use(int slot, Structure&) { return false; }          // E; false = generic level-up / upgrade
    virtual void OnMoved(Structure&) {}
    virtual void OnTeamChanged(Structure&) {}
    virtual void OnRemoved(const Structure&) {}
};
```

### Dispatcher

`StructureDispatcher` is declared right after `StructureRegistry` in `App.hpp`.

- **Registration.** `Add(StructureSystem&, Schedule)` returns a `Subscription`, where `Schedule{ std::vector<ItemKind> Kinds; int64_t IntervalMs = 0; }`. Each kind system calls it from its constructor and keeps the subscription last, in `_subs`.
- **The frame loop.** It is the only loop over structures. On each system's interval, it calls `Update` for each structure of that system's kinds, then `UpdateAll`.
- **Events.** It subscribes to the registry's events and forwards them to the system for that kind.
- **E and the card.** `Action(slot, s)` and `Use(slot, s)` look up the system for the structure's kind.

`PerStructure<T>` (in `Building/PerStructure.hpp`) is a small store, like the framework's `PerSlot`:
- It is built with `PerStructure<State> _states{structures};`.
- `operator[](const Structure&)` makes an entry on first use.
- The registry's `Moved` event resets an entry, and `Removed` drops it.

It replaces every `erase_if(FindById == nullptr)` purge, every `Moves` counter comparison and `LaserMine::DrawnFor`.

### Migrating each kind system

Each kind system derives from `StructureSystem`, drops its own timer, kind filter and purge, and keeps its behaviour.

| System | Schedule | State |
|---|---|---|
| Turret | every frame | `PerStructure<TurretState>`; the target pick staggered by id, as today |
| AirDefense | 100 ms | `PerStructure<int>` tube counter |
| RocketLauncher | every frame | `PerStructure` camera; salvos dropped in `OnRemoved` |
| Landmine, LaserMine, JumpPad | 50 ms | LaserMine: `PerStructure<Beam>`, redrawn in `OnTeamChanged` |
| Teleporter, TeslaCoil | 100 ms | none |
| SensorTower | `GlowVision::RefreshIntervalMs` | per slot, as today |
| Station | 1 s | per slot, as today |

What moves where:
- **Tesla coil:** `DestroyGrenades` goes to `UpdateAll`.
- **Rocket launcher:** `Use`, `IsFiring` and `ReloadLeft` become `Use` and `Action`.
- **Station:** `Buy` and `Offer` become `Use` and `Action`.
- **Vehicles:** boarding moves into the vehicle system (Phase 3).
- **`StructurePanel`:** its kind if-chains become `dispatcher.Action` and `dispatcher.Use`, with the generic level-up and upgrade path as the fallback. It loses the `VehicleSeats`, `RocketLauncherSystem` and `StationSystem` dependencies, and takes `StructureDispatcher` instead.
- **Teleporter:** the constructor order is fixed to App order (Hud before Structures).
- **`App::Reset`:** it loses the per-system clean-up calls. `Structures.RemoveAll()` now raises `Removed`, which clears every system's state. `Seats.ExitAll()` stays first.

### Settings clean-up

**Remove `buildMs`:**
- Delete `ItemSettings::buildMs`, `Structure::BuiltAt`, `IsBuilt`, and the time argument of `IsWorking`. `IsWorking` is then just a kind check, so delete it and let the dispatcher's kind filter replace it.
- Delete the built checks in Turret, LaserMine, Station and Teleporter, and in `Flight::CatchingNet`, which catches with any enemy net.
- Remove `buildMs` from every item in `configs/settings.jsonc`. Old server files that still have it keep loading, because unknown keys are ignored.
- Remove the `vehicle.notReady` message and translation, and the "not ready" branch in `VehicleSeats::Enter` and `StationSystem::Buy`.

**Add feature flags** to `Config/Settings.hpp`:

```cpp
struct FeatureSettings { bool tanks = true; bool helicopters = true; bool launchers = true; };
```

- **Why the defaults are `true`:** a server's existing `settings.jsonc` has only `tanks`, and the installer never overwrites it. A missing key keeps the initializer, so these defaults leave helicopters and launchers on.
- **Where the flags are applied:** `BuildSettings` (`Config/Settings.cpp`) replaces its tank-only check with `static bool Enabled(ItemKind, const FeatureSettings&)`:
  - the tank is gated by `tanks`;
  - the Ka-50 and the Huey by `helicopters`.
  - `features.launchers` empties the handheld `launchers` list (the RPG and Stinger).
  - The rocket launcher structure stays an ordinary item.
- **Where the flags are written:** in `configs/settings.jsonc`, `"features": { "tanks": true, "helicopters": true, "launchers": true }`, each with a one-line comment.
- **Why the flags don't need more code:** everything that follows comes from the settings list — shop cards, precache, and every system's behaviour. A disabled kind or weapon is simply never bought or spawned.

## Phase 3: Vehicles, one system (behaviour unchanged)

### Shape

```text
src/Assets/
  VehicleAssets.hpp        VehicleType, SeatRole, ViewMode, AimMode, ArmamentType, Steering,
                           SeatView, SeatAssets, MountAssets, ArmamentAssets, EngineSounds, GroundAssets, VehicleAssets
  VehicleCatalog.cpp       FindVehicle(kind): tank, ka50, huey, scout_drone, gun_drone (+ apc, quad_bike in phase 6)
src/Vehicles/
  Vehicle.hpp/.cpp         class Vehicle: abstract base; seats, mounts and weapons ride on the body's axes
  VehicleScope.cpp         Vehicle::Scope, Vehicle::SeatRows: a rider's HUD text
  VehicleSystem.hpp/.cpp   class VehicleSystem : StructureSystem, for every vehicle kind
  VehicleSeats.hpp/.cpp    kept: who sits where, camera prop, controls, freeze; + NextSeat()
  PilotInput.hpp           kept
  Ground/GroundVehicle.hpp/.cpp, Ground/Traction.cpp      tank, APC, quad bike (Traction = today's TankTracks.cpp)
  Air/Helicopter.*, Air/Drone.*, Air/Flight.* (namespace Flight), Air/Parachutes.*, Air/PilotTablets.*
  Parts/Mounts.*, Parts/Armament.*, Parts/Engine.*, Parts/RollingParts.*
```

Delete `Vehicles/Tank/`, `Vehicles/Helicopters/` and `Vehicles/Drones/`. `StructureAssets` loses `Seats`, `DoorOut` and `HelicopterAssets`. In `ItemKind.hpp`, delete `IsDrone` and `IsHelicopter`; `IsVehicle` becomes `FindVehicle(kind) != nullptr`.

### Data (`Assets/VehicleAssets.hpp`)

```cpp
enum class VehicleType { Ground, Helicopter, Drone };
enum class SeatRole { Driver, Gunner, Passenger };          // seat 0 is the driver
enum class ViewMode { Fixed, Chase, Sight };                // on the body / behind a part, turned with the view / along a mount
enum class AimMode { View, Crosshair, CrosshairArc };       // follow the view / at what it hits / lobbed onto it
enum class ArmamentType { Gun, Cannon, Rockets, Charge };
enum class Steering { Tracks, Wheels };

struct SeatView       { ViewMode Mode; Offset At; size_t Part = 0; int Mount = -1; };
struct SeatAssets     { SeatRole Role; Offset Feet; SeatView View; std::vector<size_t> Armament; std::string_view Caption, Title; };
struct MountAssets    { size_t YawPart, PitchPart; Offset Trunnions; float Facing, YawLeft, YawRight, PitchUp, PitchDown; AimMode Aim; bool Slow; };
struct ArmamentAssets { ArmamentType Type; int Mount = -1; Offset Muzzle; uint64_t Button = IN_ATTACK; bool Automatic; std::string_view Key; };
struct EngineSounds { std::string_view Start, Idle, Drive; Ms StartLength, IdleLength, DriveLength; };
struct GroundAssets { Steering Steer; float TrackOut; std::vector<TrackPoint> Points; std::array<std::vector<size_t>, 2> Rolling;
                      float RollSpeed; std::string_view TracksSound, TurretSound; };
struct VehicleAssets { ItemKind Kind; VehicleType Type; bool Remote; std::vector<SeatAssets> Seats; std::vector<MountAssets> Mounts;
                       std::vector<ArmamentAssets> Armament; EngineSounds Engine; GroundAssets Ground; float DoorOut = 0.0f; };
```

Vehicle entries:

| Vehicle | Seats | Mounts and weapons |
|---|---|---|
| Tank | Driver, `Chase` view on the turret | Turret and gun mount (`CrosshairArc`, `Slow`) with a `Cannon` |
| Ka-50 | Driver, `Fixed` view | Cannon mount (`Crosshair`, 50° right, 8° left) with an automatic `Gun`; `Rockets` on `IN_ATTACK2` |
| Huey | Driver; 2 Gunners with `Sight` views; 4 Passengers with `Fixed` views | Door mounts at ±90°, ±75° each, with automatic `Gun`s |
| Drones | One Driver, `Remote` | Scout: `Charge`. Gun drone: `Gun` on a `View` mount |

### Behaviour

`Vehicle` holds:
- its `VehicleAssets`, `Mounts`, `Armament` and `Engine`;
- the body's `Axes` as last placed.

Subclasses get services through their constructors.

| Member | Job |
|---|---|
| `virtual void Move(Structure&, const PilotInput* driver, float seconds) = 0` | Physics and placing the parts. |
| `virtual bool IsStopped(const Structure&) const = 0` | Whether the driver's seat may change hands. |
| `virtual void UpdateSeat(Structure&, int slot, const SeatAssets&, const PilotInput&)` | By default: aims the seat's mount, places its view and fires its armament. |
| `virtual Vector ExitSpot(const Structure&, const SeatAssets&, const VoltMod::Pawn&) const` | By default: the rider's side, then the other side, then the roof. |
| `virtual void OnExit(int slot, bool airborne)` | `Helicopter` opens a parachute here. |
| `virtual void OnRemoved()` | Blast, and stop its sounds. |
| `virtual std::string Status(int slot) const` | Adds rockets or battery after the hull line. |

The subclasses:
- **`GroundVehicle`** covers the tank here, and the APC and quad bike in Phase 6.
  - `Traction.cpp` holds `Rest`, `RestingLine`, `Step`, `Blocked`, `Outline` and `Crush`, read from `GroundAssets` and the vehicle's own hull box.
  - It is stopped below 10 u/s.
- **`Helicopter`** covers the Ka-50 and the Huey.
  - It flies, tilts, crashes, and gives the missile warning.
  - Its `ExitSpot` adds `UnderClips`.
  - It is stopped while `!Airborne`.
- **`Drone`** covers takeoff, the battery, the net, single use, and the scout's tilt and view.

The parts:
- **`Mounts`** takes today's clamp, `ShotPitch` and `TurnToward`.
- **`Armament`** takes today's `FireGun`, the tank's `Fire`, `FireRockets` and `Detonate`, all firing through the Phase 5 `ProjectileSystem::Fire`.
- **`Engine`** starts, loops idle or drive, and stops. It replaces `Rotors` and `Hum`.
- **`RollingParts`** replaces `RunTracks`.

### `VehicleSystem` as a `StructureSystem`

- **Registration and dependencies.** It registers for every vehicle kind, every frame. It takes, in App order: `Runtime, Hud, StructureRegistry, StructureDispatcher, StructureHealth, StructureAttack, ProjectileSystem, VehicleSeats, WeaponSystem`. It owns `Parachutes`.
- **The vehicle map.** `std::unordered_map<int, std::unique_ptr<Vehicle>>`:
  - `Make(assets)` switches on `VehicleType`;
  - `OnMoved` re-makes the entry;
  - `OnRemoved` calls `Vehicle::OnRemoved`, and `WatchWreck` for `Remote` vehicles.
- **`Update`:**
  1. `Move` with the driver's controls.
  2. For each rider: set the body on the seat (not `Remote`), `UpdateSeat`, `ChangeSeat` (Phase 4), then the HUD.
- **`UpdateAll`:** `PutOut()`. One `Ride` per slot replaces the tank's `_drivers` and the helicopter's `_rides`.
- **The card's E line.** `Action` and `Use` give "Board" or "Drive", and `VehicleSeats::Enter`.
- **`OnTeamChanged`** ejects every rider. `VehicleSeats::CanStay` already does this; the hook makes it immediate.

### `VehicleSeats` and the scope

- **`VehicleSeats`** keeps no kind checks:
  - The seat count comes from `FindVehicle(kind)->Seats.size()`.
  - The tablet and the "back in your body" message depend on `Remote`.
  - `WatchWreck` is public.
  - The rocket launcher still sits in it as a one-seat structure.
- **`Vehicle::Scope`** builds the scope from the rider's seat:
  - The caption and title come from the seat.
  - The status is the hull, then `Status()`.
  - The key hints are built from the seat's armament `Key`s, `keys.drive`/`turn`/`fly`/`climb`, `keys.changeSeat`, and `keys.getOut` or `keys.parachute`.
  - These replace `scope.ka50Keys`, `hueyKeys`, `gunnerKeys`, `tankKeys`, `scoutKeys` and `gunKeys` in `en` and `ru`.

## Phase 4: Changing seats and the seat HUD

- **The seat rule.** `int NextSeat(std::span<const bool> taken, int current, bool stopped)`, a free function in `VehicleSeats.hpp`:
  - it picks the next free seat, wrapping round;
  - it skips seat 0 unless the vehicle is stopped;
  - it returns -1 when there is none.
  - Test it in `tests/SeatTests.cpp`: wrap, skip the driver while moving, the driver leaving only when stopped, full.
- **R to switch.** `VehicleSystem::ChangeSeat(slot)` runs `TakePressed(slot, IN_RELOAD)`, then `NextSeat`, then `VehicleSeats::Switch(slot, seat)`.
  - `Switch` keeps the camera, freeze and controls, and discards `IN_ATTACK`.
  - It shows the messages `vehicle.stopToSwitch` and `vehicle.noFreeSeat`.
  - When the driver leaves their seat, a ground vehicle's speed goes to 0 and a landed helicopter's rotors stop.
- **Seat list panel.**
  - Markup in `stronghold_hud.xml.j2`: a container `{{screen}}_seats` holding 8 rows `{{screen}}_seat{{index}}`, each with `{s:seat{{index}}_role}` and `{s:seat{{index}}_name}`. This generates `Layout::Seats`, each with `Id`, `RoleVar` and `NameVar`.
  - `stronghold_hud/seats.css.j2`: a column at the middle right, with `seat--you`, `seat--free` and `seat--locked`.
  - `Hud::ShowSeats(slot, std::span<const SeatRow>)` and `HideSeats(slot)`. The container and rows join the pre-hide in `Ready()`.
  - The list shows only for vehicles with more than one seat, and is hidden on exit.
- **Hull bar.** `ScopeView::HullShare` drives the existing `bar` block in the scope's bottom row.
- **Target card.** It shows free seats, for example "[E] Board (3/7)".
- **Translations** in `en` and `ru`: `seat.driver`, `seat.pilot`, `seat.gunner`, `seat.passenger`, `seat.free`, `keys.changeSeat`, `vehicle.stopToSwitch`, `vehicle.noFreeSeat`.

## Phase 5: Weapons, open to new custom weapons

### Shape

```text
src/Assets/WeaponCatalog.cpp       FindWeapon(id): today's AllLaunchers(), moved out of Catalog.cpp
src/Weapons/
  WeaponSystem.hpp/.cpp            was LauncherSystem: buy, give, keep given, put away, per-slot held weapon, one frame loop
  Weapon.hpp/.cpp                  class Weapon: base for a held custom weapon
  Launcher.hpp/.cpp                class Launcher : Weapon — fires its shot along the view (RPG)
  HomingLauncher.hpp/.cpp          class HomingLauncher : Launcher — fires only once its Lock holds (Stinger)
  Lock.hpp/.cpp                    was LauncherLock: target search, progress, tones, prompt
```

### Data

`LauncherAssets` becomes `WeaponAssets`:

```cpp
enum class WeaponClass { Launcher, HomingLauncher };   // which class WeaponSystem makes
struct WeaponAssets {
    std::string_view Id; WeaponClass Class;
    std::string_view Base = "weapon_taser";             // the stock weapon it rides on; a new base gets its own vdata subclass
    std::string_view Subclass, Model, FiredBodygroup; ShotAssets Shot;
};
```

"Weapon" means a handheld weapon everywhere. A vehicle's guns are its armament: `ArmamentAssets`, `ArmamentType` and `Parts/Armament.*`, set in Phase 3.

- **Settings.** C++ `LauncherSettings` becomes `WeaponSettings`, but the JSON member stays `launchers` so operators' configs keep loading. It gains `shots` (default 1: shots per purchase).
- **Validation.** `BuildSettings` now checks:
  - `speed > 0`;
  - `lockMs > 0` for a homing weapon;
  - weapon ids don't collide with item ids, since they share the `item.`/`about.` translation keys.

### Behaviour

**`Weapon`** is one per holder, made when given. It holds the slot, its assets and settings, and `ShotsLeft`.

| Member | Job |
|---|---|
| `virtual void Aim(Frame&)` | Every frame while it is the active weapon. `HomingLauncher` runs its `Lock` here. |
| `virtual bool CanFire() const` | Defaults to `ShotsLeft > 0`. `HomingLauncher` also needs the lock to hold. |
| `virtual void Fire(Frame&)` | Launches through `ProjectileSystem::Fire`, `SetBodygroup`, and uses up a shot. |
| `virtual std::string Status(int slot) const` | HUD text: shots, lock state. |
| `virtual bool IsLockedOn(int structureId) const` | For the helicopter's missile warning. Defaults to false. |

**`WeaponSystem`** keeps today's give, `RestoreZeus` (now `KeepGiven`) and `PutAway` flow, generalised to `Base`.
- A click fires when `CanFire()`. The weapon is put away once `ShotsLeft` reaches 0.
- It subscribes to death, disconnect, team change and round start itself. This drops the hand wiring in `App.cpp` and unloads on a team change.
- `Card(slot, settings)` gives the shop each weapon card's state.

**`Lock`** keeps the target rule as a member function: an airborne enemy structure within `lockDegrees` and `range`, with line of sight. A new target rule is a new member function, not a new flag.
- Its prompt keys become `lock.searching`, `lock.aim`, `lock.locking` and `lock.locked`, with the weapon's name as a token instead of "Stinger:".

### Projectiles and the shop

- **`ProjectileSystem`.** There is one `struct Shot { Credit By; const ShotAssets* Assets; const ProjectileSettings* Flight; float Damage; }` and two makers:
  - `ShotFrom(const Structure&, float damage)`
  - `ShotFrom(int slot, const WeaponSettings&)`

  They feed `Fire(const Shot&, Vector from, Vector velocity, ProjectileKind)` and `Chase(const Shot&, Vector from, Vector velocity, ChaseTarget)`. This replaces `FireShell`/`FireRocket`/`Chase` and their launcher overloads. The callers are:
  - vehicles
  - rocket launchers
  - air defenses
  - weapons
- **Shop.**
  - `ShopCards.cpp` builds one list of products per tab, each tagged as a structure item or a weapon. `ItemCards` and `LauncherCards` merge into it.
  - `Shop::PressCard` dispatches on the tag, not on lookup order.
  - A weapon card's state comes from `WeaponSystem::Card`.

**A new weapon then needs:**
- a `WeaponCatalog.cpp` entry;
- a `settings.jsonc` entry;
- the vdata subclass, model, sounds, icon and translations;
- a new `Weapon` subclass only if it behaves differently.

## Phase 6: APC and quad bike support (no models)

- **Kinds and catalog.**
  - `ItemKind` gets `Apc` and `QuadBike`.
  - `Catalog.cpp` reserves the model paths `models/stronghold/apc/{apc,turret,gun}.vmdl` and `models/stronghold/quad_bike/quad_bike.vmdl`.
  - Placement boxes are provisional: APC about 280×110×110, quad bike about 80×45×50.
- **Wheel steering** (`Steering::Wheels`):
  - the turn rate scales with speed ÷ top speed, and flips when reversing;
  - no turning while standing still;
  - `RollingParts` plays `forward` and `reverse`.
- **`VehicleSettings::crushDamage`.** The tank's 1000 moves into its settings; 0 means players block the vehicle.
- **APC:** `Ground`, `Wheels`, with three kinds of seat:
  - Driver: `Chase` view, no weapon.
  - Gunner: `Sight` view on the turret and gun mount, aiming with the view, firing an automatic `Gun`.
  - 4 Passengers: `Fixed` views, exiting at the back.
- **Quad bike:** `Ground`, `Wheels`, with one visible Driver and a `Chase` view. `crushDamage` is 0.
- **Settings and translations.**
  - No `settings.jsonc` entries yet. The model session adds them, along with the models and the quad bike's card icon.
  - Add `item.apc`, `item.quad_bike` and `about.*` now.
- **Local check.** Add a temporary `apc` item to the local server's settings, with the APC entry pointing at the tank's parts. Don't commit it.

## Phase 7: Sounds

### Remove

Delete these events from `content/soundevents/soundevents_stronghold.vsndevts`:

| Group | Events |
|---|---|
| Build | `Build.Building`, `Build.Detect` |
| Dispenser, laser | `Dispenser.Deny`, `Laser.Beam` |
| Air | `Air.RocketIncoming`, `Air.RocketImpact3`, `Air.DefenseLaser`, `Air.DefenseFocus`, `Air.DefenseDetect`, `Air.Whoosh`, `Air.Crack` |
| Tank | `Tank.Tracks`, `Tank.Turret`, `Tank.Impact2`, `Tank.Impact3` |
| Drone | `Drone.CamOn`, `Drone.CamShutdown`, `Drone.Craft`, `Drone.Sonar` |

Delete these files:
- `build/building.mp3`, `build/detect.mp3`, `build/dispenser_deny.mp3`, `build/laser_beam.mp3`
- `air/missile_bomb.mp3`, `air/explosion_3.mp3`
- `drone/cam_on.mp3`, `drone/cam_shutdown.mp3`, `drone/craft.mp3`, `drone/sonar.mp3`
- `air/fire.mp3`, once the tank's fire sound is replaced

Also delete their compiled copies under `<CS2>/game/csgo_addons/stronghold/sounds/`.

### Add

All sounds are Freesound CC0, each licence checked on its page. They need a logged-in download. Prepare each with ffmpeg:
- trim to length;
- mono, 48 kHz, 16-bit WAV;
- peaks at -1 dBFS;
- loops of 2 to 8 s, cut at zero crossings.

| Event | File | Source |
|---|---|---|
| `Stronghold.Tank.Start` | `tank/start.wav` | adr1911 542582 |
| `Stronghold.Tank.Idle` | `tank/idle.wav` | qubodup 182793 (loop cut) |
| `Stronghold.Tank.Drive` | `tank/drive.wav` | qubodup 187676 (seamless) |
| `Stronghold.Tank.Tracks` | `tank/tracks.wav` | cognito perceptu 121531 (loop cut) |
| `Stronghold.Tank.Turret` | `tank/turret.wav` | lorefold 607311 (loop cut) |
| `Stronghold.Tank.Fire` | `tank/fire.wav` | qubodup 189344 |
| `Stronghold.Tank.Impact` | `tank/impact.wav` | unfa 231765 (resampled from 192 kHz) |
| `Stronghold.Apc.Start` | `apc/start.wav` | granconill 156358 |
| `Stronghold.Apc.Idle` | `apc/idle.wav` | kyles 637916 (loop cut) |
| `Stronghold.Apc.Drive` | `apc/drive.wav` | kyles 405086 (loop cut) |
| `Stronghold.Apc.Fire` | `apc/fire.wav` | qubodup 854186 (a different shot from the Ka-50 cannon's) |
| `Stronghold.Quad.Start` | `quad_bike/start.wav` | Alex_hears_things 379915 |
| `Stronghold.Quad.Idle` | `quad_bike/idle.wav` | mickyman5000 340670 |
| `Stronghold.Quad.Drive` | `quad_bike/drive.wav` | Flares.fr 671044 |

- **Fallbacks:** monosfera 572294 for the tank idle, qubodup 239135 for the tank shot.
- **Avoid:** Pixabay (it restricts redistribution), craigsmith's vintage tank sounds, GaryQ 127845, and qubodup 200303 (CC-BY).

### Events, wiring and docs

- **Event blocks.**
  - Engine loops: `csgo_mega`, mixgroup `Ambient`, falloff from 250 to 2200.
  - Shots: mixgroup `Explosions`, falloff from 250 to 4200.
  - Store the lengths in `EngineSounds`.
- **Wiring.**
  - The engines run through `Engine`: idle while stopped, drive loop above 20% of top speed.
  - `Tank.Tracks` plays while `RollingParts` runs.
  - `Tank.Turret` plays while the turret turns faster than 5°/s.
  - `Tank.Fire` and `Tank.Impact` go on the tank's `ShotAssets`.
- **Compile and document.**
  - Compile with `--install client --install server`, and refresh `server-assets/soundevents/*.vsndevts_c`.
  - Update `docs/assets.md`: authors, ids, CC0, and credit for qubodup.

---

## Execution

### Branches

- Create a new branch `refactor/vehicles-structures-weapons` from `main` in each repo that changes:
  - the `plugins/stronghold` repo: code, content, docs;
  - the `cs2-plugins` root: the `3d-model` skill script and `SKILL.md`, plus the stronghold pointer if it is tracked.
- voltmod is not expected to change. If it does, it gets the same branch name, and it is committed before the plugin.
- No release, relock or push to `prod`. Commit through the `/commit` skill, inner repos first, only when the user asks to push.

### Grouped commits

Commit each phase once its build, tests and lint pass.

| Commit | Repo | Contents |
|---|---|---|
| `feat: set model scale in the vmdl writer` | cs2-plugins | `modeldoc.py`, `SKILL.md` |
| `refactor: bake vehicle scale into the models` | stronghold | Phase 1: vmdls, compiled server assets, code offsets |
| `refactor: run structures through one dispatcher with lifecycle events` | stronghold | Phase 2, the dispatcher |
| `refactor: drop buildMs and gate helicopters and launchers behind features` | stronghold | Phase 2, settings clean-up |
| `refactor: one vehicle system with data-driven seats, mounts and armament` | stronghold | Phase 3 |
| `feat: change seats with R and show the crew on the HUD` | stronghold | Phase 4 |
| `refactor: weapon classes, one projectile shot and one shop product list` | stronghold | Phase 5 |
| `feat: add APC and quad bike support` | stronghold | Phase 6 |
| `chore: remove unused sounds` | stronghold | Phase 7, the deletions |
| `feat: CC0 engine, track, turret and shot sounds for tank, APC and quad bike` | stronghold | Phase 7, the additions and wiring |

### What goes to subagents

The C++ phases share one build tree, one CMake configure, and the same hot files: `App.hpp`, `Catalog.cpp`, `ItemSettings.hpp` and the translations. They run one after another in the main tree. The asset work doesn't touch C++, so it runs alongside.

**Wave 1, in parallel from the start** (background agents):

- **Sounds agent** (`general-purpose`), Phase 7 content only:
  - delete the unused events and files;
  - fetch the CC0 originals (if Freesound needs a login, stop and report the list for the user to download);
  - trim and loop them with ffmpeg;
  - add the new `vsndevts` blocks, compile, and update the sound rows in `docs/assets.md`.

  It reports each file's length for `EngineSounds`. It must not touch `src/`.
- **Models agent** (`general-purpose`, uses the `3d-model` skill and the Blender MCP), Phase 1 content only:
  - add `scale` to `modeldoc.py` and update `SKILL.md`;
  - add the scale modifier to the tank, Ka-50 and Huey vmdls, then compile for client and server;
  - check the hulls in Source2Viewer;
  - measure in Blender the roof heights over every seat at the new scale.

  It reports the seat feet heights that keep a 72-unit rider's head under the roof. It must not touch `src/`.
- **Main agent:** applies the Phase 1 code changes (remove the runtime scale, write offsets at final size), then takes the head-room numbers from the models agent.

**Wave 2, one after another in the main tree.** Hand each phase to a fresh `general-purpose` subagent in the foreground, with the phase section of this plan as its brief. That gives each phase a clean context. Order: Phase 2, then 3, then 4, then 5, then 6.

After each phase:
- the main agent runs `/build-local`, `poe test` and `poe lint`;
- the main agent reads the diff;
- an `Explore` agent in the background checks the finished phase against its section: no kind checks left, no dead files, names as planned. This runs while the next phase starts.

**Wave 3:**
- Wire the Phase 7 engine, track and turret sounds into `Engine` and `RollingParts`, using the sounds agent's lengths.
- Run `/code-review` on the whole branch and fix what it confirms.
- Run a final pass on the local server: `uv run poe run stronghold` (build, install, launch), then play through the verification list below. There is no remote deploy; `/deploy-test` and prod are left to the user.

## Critical files

**Modify:**
- `src/Assets/*`
- `src/Building/*`
- `src/Structures/**`
- `src/Vehicles/VehicleSeats.*`
- `src/Weapons/*`
- `src/Projectiles/*`
- `src/Economy/Shop/*`
- `src/Ui/Hud.*`
- `src/App.*`
- `src/Config/{ItemSettings,Settings}.*`
- `panorama/screens/stronghold_hud*`
- `translations/{en,ru}.json`
- `content/soundevents/*.vsndevts`
- `content/models/stronghold/{tank,ka50,huey}/*.vmdl`
- `docs/assets.md`
- `.claude/skills/3d-model/scripts/modelkit/modeldoc.py` and `SKILL.md`

**New:**
- Phase 2: `StructureSystem.hpp`, `StructureDispatcher.*`, `PerStructure.hpp`
- Phase 3: the vehicle tree
- Phase 5: `Weapon.*`, `Launcher.*`, `HomingLauncher.*`, `Lock.*`, `WeaponCatalog.cpp`
- Tests: `tests/SeatTests.cpp`

**Reuse:**
- `Math::*` in `src/Math/`
- the `Flight` functions
- `StructureAttack::{ShootGun,Strike,StrikePart,Blast}` and `StructureHealth::Destroy`
- `SpawnBlast`, `Pawns::*`, `Text::*`, `FrameClock`, `KeyPresses`
- VoltMod's `Event`/`Subscription` pattern, and `PerSlot` as the model for `PerStructure`

## Verification

**Every phase:** run `/build-local`, `uv run poe test` and `uv run poe lint`. Check in game on the local server: quit, install, `--start`, then reconnect.

- **Phase 1**
  - The tank and helicopters are smaller and their parts line up.
  - Their hulls stop at walls.
  - No head shows through a roof.
  - The tracks run at ground speed.
  - The ghost matches the placed structure.
- **Phase 2**, each kind behaving as before:
  - Turrets target, fire, level up and take upgrades.
  - Air defense intercepts.
  - The rocket launcher salvo runs from E.
  - Landmines and laser mines work, and a laser mine redraws its beam after a move and in the new colour after sabotage.
  - Jump pads launch without landing damage.
  - Sensor towers reveal.
  - Stations sell.
  - Teleporters pair, send and remove together.
  - Tesla coils repair and zap grenades.
  - Moving and removing a structure clears its state.
  - Sabotage re-skins the structure and hides a landmine from its new enemies.
  - Removing a sabotaged teleporter exit refunds nothing of the entrance.
  - Every structure works as soon as it is placed.
  - Settings with `features.helicopters: false` remove the Ka-50 and Huey cards; `features.launchers: false` removes the RPG and Stinger cards.
  - A settings file without the new flags keeps everything on.
- **Phase 3:** the tank, Ka-50, Huey and drones behave as before, and both ways out work.
- **Phase 4**
  - R cycles the Huey's seats in flight but refuses the pilot seat.
  - On the ground the pilot can swap seats.
  - The seat list and the target card's seat count update.
- **Phase 5**
  - The RPG fires straight.
  - The Stinger locks onto aircraft only, with its tones and prompt.
  - A helicopter warns while locked on.
  - A team change unloads the launcher.
  - Shop cards buy and put back as before.
  - A test entry with `shots: 3` fires three times.
- **Phase 6:** the temporary APC steers on wheels, its gunner fires while someone else drives, and R swaps seats.
- **Phase 7:** the new tank sounds play, no event is left unreferenced, and the addon has no deleted files.
- **End:** replay the whole list on the local server (`uv run poe run stronghold`), with `rcon-debug` for server-side checks. There is no remote deploy.
