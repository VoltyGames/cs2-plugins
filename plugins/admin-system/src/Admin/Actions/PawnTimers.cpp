#include "Admin/Actions/PawnTimers.hpp"

#include <VoltMod/Runtime.hpp>
#include <random>

namespace AdminSystem::Admin::Actions
{

namespace Log = VoltMod::Log;

static float Jitter(float range)
{
    static std::mt19937 generator{std::random_device{}()};
    return std::uniform_real_distribution<float>(-range, range)(generator);
}

PawnTimers::PawnTimers(VoltMod::Runtime& runtime) : _runtime(runtime), _timers(runtime.Slots)
{
    if (auto available = _runtime.Damage.Available(); !available)
    {
        Log::Warn("Slapped players will take fall damage: {}", available.error().Detail);
        return;
    }
    _damage = _runtime.Damage.Before += [this](VoltMod::DamageHit& hit) { OnDamage(hit); };
}

void PawnTimers::Slap(const VoltMod::Pawn& pawn, float upward, float horizontal, int fallProtectMs)
{
    pawn.SetVelocity(Vector{Jitter(horizontal), Jitter(horizontal), upward});

    const int slot = pawn.Slot();
    if (fallProtectMs <= 0 || !VoltMod::IsValidSlot(slot))
    {
        return;
    }

    Timers& timers = _timers[slot];
    timers.Slapped = pawn.Ref();
    timers.FallSafeUntil = std::chrono::steady_clock::now() + std::chrono::milliseconds(fallProtectMs);
}

void PawnTimers::OnDamage(VoltMod::DamageHit& hit)
{
    if (!(hit.Type & VoltMod::DamageFall))
    {
        return;
    }
    const int slot = hit.Victim.AsPawn().Slot();
    if (!VoltMod::IsValidSlot(slot))
    {
        return;
    }
    const auto& timer = _timers[slot];
    if (hit.Victim.Ref() == timer.Slapped && std::chrono::steady_clock::now() < timer.FallSafeUntil)
    {
        hit.Blocked = true;
    }
}

void PawnTimers::SlayAfter(int slot, int64_t delayMs)
{
    if (!VoltMod::IsValidSlot(slot))
    {
        return;
    }

    _timers[slot].Slay = _runtime.Scheduler.Delay(delayMs, [this, slot] {
        if (const VoltMod::Pawn pawn = _runtime.Entities.Pawn(slot); pawn.IsAlive())
        {
            pawn.Slay();
        }
    });
}

}  // namespace AdminSystem::Admin::Actions
