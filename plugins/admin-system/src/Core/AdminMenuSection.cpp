#include "Core/AdminMenuSection.hpp"

#include <VoltMod/Api.hpp>

namespace AdminSystem::Core
{

void AdminMenuSection::Publish()
{
    _published = _runtime.Exchange.Publish<Contracts::IMenuSection>(this, "admin");
}

bool AdminMenuSection::IsVisibleTo(int slot)
{
    const VoltMod::Player* player = _runtime.Players.Get(slot);
    return player && _admins.IsAdmin(player->SteamId());
}

bool AdminMenuSection::Open(int slot)
{
    return IsVisibleTo(slot) && _openMenu(slot);
}

}  // namespace AdminSystem::Core