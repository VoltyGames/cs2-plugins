#pragma once

#include "Admin/AdminManager.hpp"

#include <Contracts/IMenuSection.hpp>
#include <VoltMod/Api.hpp>
#include <VoltMod/Core/Signals/Subscription.hpp>
#include <functional>

namespace AdminSystem::Core
{

/** The main menu's "admin" entry: shown to admins, opens the admin menu. */
class AdminMenuSection final : public Contracts::IMenuSection
{
public:
    /** @p openMenu opens the admin menu, which reaches the whole App; false when it could not be built. */
    AdminMenuSection(VoltMod::Runtime& runtime, Admin::AdminManager& admins, std::function<bool(int)> openMenu)
        : _runtime(runtime), _admins(admins), _openMenu(std::move(openMenu))
    {}

    /** Offer this to other plugins until this is destroyed. */
    void Publish();

    bool IsVisibleTo(int slot) override;
    bool Open(int slot) override;

private:
    VoltMod::Runtime& _runtime;
    Admin::AdminManager& _admins;
    std::function<bool(int)> _openMenu;
    /** Declared last, so the entry is withdrawn before anything it reaches. */
    VoltMod::Subscription _published;
};

}  // namespace AdminSystem::Core