#pragma once

#include <VoltMod/App/Config.hpp>
#include <string>
#include <vector>

namespace MainMenu
{

/** One row of a tab. `kind` says which of the target fields it reads. */
struct EntrySettings
{
    /** "command", "link" or "section". */
    std::string kind;
    /** A translation key, or literal text when no translation has that key. */
    std::string label;
    /** For "command": a console command run as the player, such as `mm_lvl`. */
    std::string command;
    /** For "link": printed to the player's chat; a server cannot open a browser. */
    std::string url;
    /** For "section": the id another plugin publishes a Contracts::IMenuSection under. */
    std::string section;
};

struct TabSettings
{
    std::string label;
    /** One of the names in panorama/screens/main_menu/icons.j2. */
    std::string icon;
    std::vector<EntrySettings> entries;
};

struct Settings
{
    VoltMod::StandardPluginSettings plugin;
    /** The workshop addon every connecting client must download; 0 requires none. */
    uint64_t addonId = 0;
    VoltMod::PanoramaMenuSettings menu{.panorama = true};
    std::vector<TabSettings> tabs;
};

enum class EntryKind
{
    Command,
    Link,
    Section
};

/** An entry that passed CleanSettings. */
struct Entry
{
    EntryKind kind = EntryKind::Command;
    std::string label;
    /** The command, the url, or the section id. */
    std::string target;
};

struct Tab
{
    std::string label;
    std::string icon;
    std::vector<Entry> entries;
};

struct Hub
{
    VoltMod::StandardPluginSettings plugin;
    uint64_t addonId = 0;
    VoltMod::PanoramaMenuSettings menu;
    std::vector<Tab> tabs;
};

/** The layout draws no more tabs than this. */
inline constexpr int MaxTabs = 7;

/** Drops entries with an unknown kind or an unusable target, and tabs past MaxTabs, logging each. */
Hub CleanSettings(Settings raw);

using ConfigManager = VoltMod::Options<Settings, Hub>;

}  // namespace MainMenu
