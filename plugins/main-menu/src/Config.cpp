#include "Config.hpp"

#include <VoltMod/App/Config/Validation.hpp>
#include <VoltMod/Core/Log.hpp>
#include <cstddef>
#include <format>
#include <optional>
#include <string>
#include <string_view>
#include <utility>

namespace Log = VoltMod::Log;
namespace Validation = VoltMod::Validation;

namespace MainMenu
{

static std::optional<EntryKind> ParseKind(std::string_view kind)
{
    if (kind == "command")
    {
        return EntryKind::Command;
    }
    if (kind == "link")
    {
        return EntryKind::Link;
    }
    if (kind == "section")
    {
        return EntryKind::Section;
    }
    return std::nullopt;
}

static std::optional<std::string> EntryProblem(const EntrySettings& entry)
{
    if (entry.label.empty())
    {
        return "no label";
    }

    const std::optional<EntryKind> kind = ParseKind(entry.kind);
    if (!kind)
    {
        return std::format("unknown kind '{}'", entry.kind);
    }

    switch (*kind)
    {
    case EntryKind::Command:
        // The command runs as one console line; a separator would smuggle in a second one.
        if (entry.command.empty() || entry.command.find_first_of(";\r\n") != std::string::npos)
        {
            return std::format("command '{}' must be one console command", entry.command);
        }
        break;
    case EntryKind::Link:
        if (!entry.url.starts_with("https://") && !entry.url.starts_with("http://"))
        {
            return std::format("url '{}' must start with http:// or https://", entry.url);
        }
        break;
    case EntryKind::Section:
        if (entry.section.empty())
        {
            return "no section id";
        }
        break;
    }
    return std::nullopt;
}

static Entry ToEntry(EntrySettings raw)
{
    const EntryKind kind = *ParseKind(raw.kind);
    std::string& target = kind == EntryKind::Command ? raw.command : kind == EntryKind::Link ? raw.url : raw.section;
    return Entry{.kind = kind, .label = std::move(raw.label), .target = std::move(target)};
}

Hub CleanSettings(Settings raw)
{
    if (raw.tabs.size() > static_cast<std::size_t>(MaxTabs))
    {
        Log::Warn("tabs: only the first {} of {} are shown", MaxTabs, raw.tabs.size());
        raw.tabs.resize(static_cast<std::size_t>(MaxTabs));
    }

    Hub hub{.plugin = std::move(raw.plugin), .addonId = raw.addonId, .menu = raw.menu};
    for (TabSettings& tab : raw.tabs)
    {
        Validation::FilterValid(
            tab.entries, [](const EntrySettings& entry, std::size_t) { return EntryProblem(entry); },
            std::format("tabs.{}.entries", tab.label));

        Tab& clean = hub.tabs.emplace_back(Tab{.label = std::move(tab.label), .icon = std::move(tab.icon)});
        for (EntrySettings& entry : tab.entries)
        {
            clean.entries.push_back(ToEntry(std::move(entry)));
        }
    }
    return hub;
}

}  // namespace MainMenu
