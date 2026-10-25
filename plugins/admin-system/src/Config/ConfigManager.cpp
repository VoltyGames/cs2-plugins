#include "Config/ConfigManager.hpp"

#include <VoltMod/App/Config/Validation.hpp>
#include <VoltMod/Core/Text/EnumNames.hpp>
#include <algorithm>
#include <cstddef>
#include <format>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using VoltMod::ParseDuration;
namespace Validation = VoltMod::Validation;

namespace AdminSystem::Config
{

// maps.cycle and weapons.menu are the same shape of list: convert the raw config rows to their
// runtime type, drop the ones their domain check rejects, and fall back to the struct defaults
// when nothing valid is left - an empty Map or Give page reads as a broken plugin rather than as
// a configuration gap, most often on a server whose settings.jsonc predates the section.
// Whether a map file exists is the engine's call; MapCycleState re-checks the resolved names at
// load so a stale entry surfaces in the load report.
template <class Entry, class Raw, class ToEntry>
static std::vector<Entry> ResolveList(const std::vector<Raw>& rows, const std::vector<Raw>& defaults, ToEntry toEntry,
                                      std::string (*validate)(const Entry&), std::string_view what)
{
    auto build = [&](const std::vector<Raw>& source) {
        std::vector<Entry> entries;
        entries.reserve(source.size());
        for (const auto& row : source)
        {
            entries.push_back(toEntry(row));
        }

        Validation::FilterValid(
            entries,
            [validate](const Entry& entry, std::size_t) -> std::optional<std::string> {
                auto problem = validate(entry);
                if (problem.empty())
                {
                    return std::nullopt;
                }
                return problem;
            },
            what);
        return entries;
    };

    auto entries = build(rows);
    Validation::FallbackIfEmpty(entries, [&] { return build(defaults); }, what);
    return entries;
}

ConfigManager::ConfigSnapshot ConfigManager::BuildSnapshot(Settings raw)
{
    ConfigSnapshot snapshot{.Values = std::move(raw)};
    auto& settings = snapshot.Values;

    Validation::NormalizeTag(settings.server.tag, 64, "default", "server.tag");

    auto& punishments = settings.punishments;
    Validation::FilterValid(
        punishments.templates,
        [](const PunishmentTemplate& t, std::size_t) -> std::optional<std::string> {
            auto type = Punishments::ParsePunishType(t.type);
            if (!type || !Punishments::LookUp(*type).Timed)
            {
                return std::format("type must be ban/voiceMute/textMute, got '{}'", t.type);
            }
            if (ParseDuration(t.duration) < 0)
            {
                return std::format("bad duration '{}'", t.duration);
            }
            if (t.name.empty() || t.reason.empty())
            {
                return std::string("name and reason must be non-empty");
            }
            return std::nullopt;
        },
        "punishments.templates");

    snapshot.Templates.reserve(punishments.templates.size());
    for (const auto& t : punishments.templates)
    {
        snapshot.Templates.push_back(
            {t.name, *Punishments::ParsePunishType(t.type), ParseDuration(t.duration), t.reason});
    }

    // An empty duration picker would dead-end the menu ban/mute flow; the helper falls back to
    // the struct defaults so the list exists in exactly one place.
    snapshot.MenuDurationSecs = Validation::ParseDurations(
        punishments.menuDurations, PunishmentSettings{}.menuDurations, "punishments.menuDurations");

    auto& reports = settings.reports;
    Validation::FilterValid(
        reports.reasons,
        [](const ReportReason& r, std::size_t) -> std::optional<std::string> {
            if (r.code.empty() || r.label.empty())
            {
                return std::string("code and label must be non-empty");
            }
            if (r.code.size() > 32)
            {
                return std::format("code '{}' is longer than 32 chars", r.code);
            }
            return std::nullopt;
        },
        "reports.reasons");
    Validation::FallbackIfEmpty(reports.reasons, [] { return ReportSettings{}.reasons; }, "reports.reasons");
    reports.cooldownSec = std::max(reports.cooldownSec, 0);
    reports.duplicateWindowSec = std::max(reports.duplicateWindowSec, 0);

    snapshot.Maps = ResolveList<Maps::MapEntry>(
        settings.maps.cycle, MapSettings{}.cycle,
        [](const MapConfigEntry& e) {
            return Maps::MapEntry{.Name = e.name, .DisplayName = e.displayName, .WorkshopId = e.workshopId};
        },
        Maps::ValidateMapEntry, "maps.cycle");

    snapshot.Weapons = ResolveList<Weapons::WeaponEntry>(
        settings.weapons.menu, WeaponSettings{}.menu,
        [](const WeaponConfigEntry& e) { return Weapons::WeaponEntry{.Name = e.name, .Item = e.item}; },
        Weapons::ValidateWeaponEntry, "weapons.menu");

    return snapshot;
}

}  // namespace AdminSystem::Config
