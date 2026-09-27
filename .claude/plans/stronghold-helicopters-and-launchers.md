# Stronghold helicopters and launchers

Status: planned 2026-09-27, outline only. Not started. Card art and concept sheets are committed
(stronghold `2f6933a`): `panorama/images/stronghold/{attack_helicopter,transport_helicopter,rpg,anti_air}.png`
and `docs/concepts/*.jpg`.

## Goal

Four new shop items:

| Item | Id | Real analogue | Kind |
|---|---|---|---|
| Attack helicopter | `attack_helicopter` | Ka-50: one pilot, coaxial rotors, side cannon, rocket pods | Structure, vehicle |
| Transport helicopter | `transport_helicopter` | UH-1H Huey: pilot, 2 door gunners, 4 passengers | Structure, vehicle |
| RPG | `rpg` | RPG-7 | Player weapon |
| Anti-air launcher | `anti_air` | FIM-92 Stinger | Player weapon |

The anti-air launcher is the player-side counter to helicopters and drones. Ship it together with the
attack helicopter.

## Facts this plan relies on

- A new vehicle kind is wired by: the `ItemKind` enum, `IsVehicle`/`IsDrone` in
  `src/Assets/ItemKind.hpp`, a `StructureAssets` entry and `ParseItemKind` in `src/Assets/Catalog.cpp`, an
  item in `configs/settings.jsonc` (price, limit, levels, `vehicle{}`), `item.<id>` plus the about
  text in `translations/{en,ru}.json`, the card png, and the model under `addon/models/stronghold/<id>/`.
- `VehicleSeats` keeps one seat per player slot, but `Enter` refuses when `Pilot(vehicleId) >= 0`, so
  a vehicle holds exactly one player. The body stays frozen where the player got in, and the view comes from a
  camera prop.
- `DroneSystem` flight (`DroneFlight.cpp` `Advance`) already caps height above the floor and slides
  along walls; `DroneWeapons` fires hitscan where the pilot looks.
- `ProjectileSystem` shots carry a `SourceId` structure. Credit and damage go through
  `StructureAttack` by structure id, and a shot whose structure is gone hurts nobody. There is no
  player-owned shot.
- `ProjectileSystem::Chase` with a target structure is the homing interceptor `AirDefenseSystem`
  fires at drones, with a `turnRate` so the target can dodge.
- Player equipment (`EquipmentSettings`, `LoadoutSystem::Buy`) gives a stock item by name. Its shop
  tiles are a fixed 5, drawn with built-in CS2 icons (`stronghold_menu/art.j2`), not the png cards.
- VoltMod has `WeaponFire` and `BulletImpact` events, `Entity::SetGravityScale`, `SetVelocity` and
  `Teleport`. Stronghold uses none of the weapon events yet.
- Anticheat has no exemption contract; it knows nothing about seated players.

## Phase 1: attack helicopter

A single-seat vehicle built on the drone code.

- New `ItemKind::AttackHelicopter`, counted by `IsVehicle` and flown by the drone flight code (either
  count it in `IsDrone` or split out an `IsAircraft`).
- `DroneSystem` gains the helicopter's weapons: the side cannon through `DroneWeapons`, and rockets
  fired straight ahead as a new direct-fire shot kind in `ProjectileSystem`.
- No battery run-out. Keep `lifetimeMs` large or treat 0 as unlimited, and rely on health.
- Flight feel: more momentum and lower acceleration than a drone; the model banks into its velocity
  while traces keep the upright hull.
- A higher `vehicle.maxHeight`; check each map's skybox.
- Air defenses and nets already target drones; include the helicopter wherever they pick targets.
- Model: build from `docs/concepts/attack_helicopter.jpg` with the `3d-model` skill. Use two stacked
  3-blade rotors (the sheet's top view is wrong) spun by an animation, and the cannon as its own part
  aimed like the gun drone's.
- Sounds: rotor loop, cannon, rocket launch.

## Phase 2: player-owned shots

Needed by both handheld weapons.

- A `Shot` gets an owner that is either a structure or a player (`PlayerRef` plus team).
- `StructureAttack` gets entry points that credit a player directly, next to the structure-id ones.
- Direct-fire rockets (from phase 1) are not intercepted by air defenses, like shells.

## Phase 3: RPG

- **Spike first:** choose the stock weapon to repurpose. Zeus x27 is the likely fit: its own slot, so
  it doesn't replace the free rifle set, and one shot per purchase. Check whether its world model can be
  swapped, and whether an addon override of its viewmodel works (it would change every Zeus). If not,
  accept the stock viewmodel.
- On `WeaponFire` for that weapon from a slot that bought the RPG, fire a player-owned direct-fire
  rocket from the eyes along the aim, and cancel the weapon's own hit (for example, by blocking its
  damage in the damage hook).
- Shop: a new equipment tile with the png card. The loadout's fixed 5 gear tiles grow, or launchers
  get their own row.
- Ammo: one rocket per purchase, or a refill at the ammo station.
- Model: `docs/concepts/rpg.jpg`, world model only.

## Phase 4: anti-air launcher

- Same base-weapon approach as the RPG (a separate stock weapon if both can be carried).
- Lock-on: while it is held, aimed within a few degrees of an enemy aircraft in sight (trace check),
  and inside range, a lock fills over about 1.5 s. The HUD shows the lock and plays a rising tone. Fire only
  on a full lock; the lock breaks when the aim drifts.
- Fire a player-owned interceptor through `ProjectileSystem::Chase` at the target structure.
- The target pilot's scope shows a "missile lock" warning while locked and while the missile flies.
- Optional: flares, a pilot key that sends chasing interceptors to a decoy point.

## Phase 5: transport helicopter

The largest change, because it needs several seats per vehicle and crews whose bodies travel with the
helicopter.

- `VehicleSeats` gets a seat index per vehicle: pilot, left gunner, right gunner, 4 passengers.
  `Pilot(vehicleId)` becomes a lookup by seat. E near a helicopter takes the first free seat, or one
  chosen by where the player stands.
- Riding bodies: each frame, teleport every seated pawn to its seat's offset on the helicopter (still
  frozen). Other players see and can shoot the crew in the doors.
- Door gunners: each gets a camera at their gun with a limited yaw and pitch arc, and fires hitscan through
  `DroneWeapons`. The gun part turns with their aim.
- Passengers: a camera looking out of the cabin; E exits.
- Exit in the air (parachute): unfreeze at the seat position, carry over the helicopter's velocity,
  then cap the fall speed each frame (or lower `GravityScale`) until the player lands. The parachute model is
  attached to the pawn; reuse the supply crate's parachute.
- Hull versus players: a large prop moved by teleport does not push players. Refuse landing while a
  player is under the helicopter, or let crews board by pressing E near it while it hovers low.
- Model: `docs/concepts/transport_helicopter.jpg`. Guns on posts inside the doorways at the rear edge,
  a bench for four, a two-blade rotor.

## Across phases

- **Anticheat:** seated players teleported every frame and slowed parachute falls can look like
  movement cheats. Add a small contract (for example, `Contracts::IPlayerExemptions`) that stronghold
  publishes and anticheat asks before judging movement. Check whether anything actually trips it
  before building it.
- **MovementFreeze stacking** (latent): two holders on one pawn restore the wrong move type. The
  transport's riders make a second holder more likely; fix it with a per-pawn count in the host
  first if needed.
- **Balance:** helicopter prices and limits, and anti-air damage per level, go in
  `configs/settings.jsonc`. Remember that installing never overwrites a server's existing settings file.
- **Assets:** add rows for the new models to `docs/assets.md` as each one lands.

## Open questions

- Which stock weapons can carry the two launchers, and can their models be replaced? This is the phase 3 spike.
- Do seated players who are teleported every frame look smooth to other clients? Test with two clients.
- Map scale: are the Stronghold maps tall and open enough for the Huey?
