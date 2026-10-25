#pragma once

#include "Core/Permissions.hpp"

#include <array>
#include <cstddef>
#include <span>
#include <string_view>

namespace AdminSystem::Admin::Menu
{

/** Every row the admin panel can draw, in the order its tab draws them. Free of the game SDK, so
 *  `MenuCatalogTests` can link it. */
enum class RowId
{
    // Punish
    LiftList,
    PunishPlayers,
    LiftBans,
    LiftMutes,
    PunishKick,
    PunishBan,
    PunishVoiceMute,
    PunishTextMute,
    PunishWarn,
    // Player Actions
    CheatCheck,
    Kill,
    Bring,
    Goto,
    Swap,
    Freeze,
    Noclip,
    Bury,
    Unbury,
    ChangeTeam,
    Speed,
    Slap,
    Health,
    Armor,
    Godmode,
    Weapons,
    // Player Fun
    Ghost,
    Disco,
    Wallhack,
    Model,
    Bhop,
    Drunk,
    Smite,
    Size,
    // Map & Vote
    ChangeMap,
    SetNextMap,
    VoteMap,
    CancelVote,
    // My Settings
    Hide,
    ChatPrefix,
    NameColor,
    MessageColor,
};

/** One row of one menu. An empty @ref Permission means any registered admin; a non-empty
 *  @ref Children makes the row visible exactly when one of its children is, so a list that would
 *  open empty is never offered. */
struct RowSpec
{
    RowId Id;
    std::string_view LabelKey;
    std::string_view Permission;
    std::span<const RowSpec> Children;
};

/** The punishment kinds the merged lift list may show, each with the permission that lifts it. */
inline constexpr RowSpec LiftBansRow{RowId::LiftBans, "action.unban", Permission::Unban, {}};
inline constexpr RowSpec LiftMutesRow{RowId::LiftMutes, "action.unmute", Permission::Mute, {}};

inline constexpr std::array<RowSpec, 2> LiftRows{{LiftBansRow, LiftMutesRow}};

/** The player card under the Punish tab, mirroring `Punishments::PunishTypes` row for row:
 *  this permission decides what an admin sees, that one what the dispatcher accepts. */
inline constexpr std::array<RowSpec, 5> PunishCardRows{{
    {RowId::PunishKick, "action.kick", Permission::Kick, {}},
    {RowId::PunishBan, "action.ban", Permission::Ban, {}},
    {RowId::PunishVoiceMute, "action.voiceMute", Permission::Mute, {}},
    {RowId::PunishTextMute, "action.textMute", Permission::Mute, {}},
    {RowId::PunishWarn, "action.warn", Permission::Mute, {}},
}};

/** The one drawn row of the Punish tab; the rest of it is one row per connected player. */
inline constexpr RowSpec PunishLiftList{RowId::LiftList, "punish.activeList", {}, LiftRows};

/** The player rows only lead to the card, so the tab is worth showing when any card row is. */
inline constexpr RowSpec PunishPlayerList{RowId::PunishPlayers, "category.punish", {}, PunishCardRows};

inline constexpr std::array<RowSpec, 2> PunishTabRows{{PunishLiftList, PunishPlayerList}};

inline constexpr std::array<RowSpec, 16> PlayerActionRows{{
    {RowId::CheatCheck, "action.cheatCheck", Permission::Control, {}},
    {RowId::Kill, "action.kill", Permission::Control, {}},
    {RowId::Bring, "action.bring", Permission::Control, {}},
    {RowId::Goto, "action.goto", Permission::Control, {}},
    {RowId::Swap, "action.swap", Permission::Control, {}},
    {RowId::Freeze, "action.freeze", Permission::Control, {}},
    {RowId::Noclip, "action.noclip", Permission::Control, {}},
    {RowId::Bury, "action.bury", Permission::Control, {}},
    {RowId::Unbury, "action.unbury", Permission::Control, {}},
    {RowId::ChangeTeam, "action.changeTeam", Permission::Control, {}},
    {RowId::Speed, "action.speed", Permission::Control, {}},
    {RowId::Slap, "action.slap", Permission::Control, {}},
    {RowId::Health, "action.health", Permission::Health, {}},
    {RowId::Armor, "action.armor", Permission::Health, {}},
    {RowId::Godmode, "action.godmode", Permission::Health, {}},
    {RowId::Weapons, "action.giveWeapon", Permission::Weapon, {}},
}};

inline constexpr std::array<RowSpec, 8> PlayerFunRows{{
    {RowId::Ghost, "action.ghost", Permission::Fun, {}},
    {RowId::Disco, "action.disco", Permission::Fun, {}},
    {RowId::Wallhack, "action.wallhack", Permission::Wallhack, {}},
    {RowId::Model, "action.model", Permission::Fun, {}},
    {RowId::Bhop, "action.bhop", Permission::Bhop, {}},
    {RowId::Drunk, "action.drunk", Permission::Fun, {}},
    {RowId::Smite, "action.smite", Permission::Fun, {}},
    {RowId::Size, "action.size", Permission::Fun, {}},
}};

inline constexpr std::array<RowSpec, 4> MapVoteRows{{
    {RowId::ChangeMap, "action.changeMap", Permission::Map, {}},
    {RowId::SetNextMap, "action.setNextMap", Permission::Map, {}},
    {RowId::VoteMap, "action.voteMap", Permission::Vote, {}},
    {RowId::CancelVote, "action.cancelVote", Permission::Vote, {}},
}};

inline constexpr std::array<RowSpec, 4> MySettingsRows{{
    {RowId::Hide, "action.hide", Permission::Hide, {}},
    {RowId::ChatPrefix, "chat.displayPrefix", {}, {}},
    {RowId::NameColor, "chat.nameColor", {}, {}},
    {RowId::MessageColor, "chat.messageColor", {}, {}},
}};

enum class TabId
{
    Punish,
    PlayerActions,
    PlayerFun,
    RoundModes,
    MapVote,
    MySettings,
};

/** One tab of the panel. A tab that lists @ref Rows is visible exactly when one of them is, so it
 *  cannot outlive its contents; one whose contents are declared elsewhere names its own
 *  @ref Permission instead. */
struct TabSpec
{
    TabId Id;
    std::string_view LabelKey;
    /** One of the six names generated into panorama/screens/admin_menu/icons.j2. Reusing an
     *  existing name keeps a menu change out of the workshop publish queue. */
    std::string_view Icon;
    std::string_view Permission;
    std::span<const RowSpec> Rows;
};

inline constexpr std::array<TabSpec, 6> Tabs{{
    {TabId::Punish, "category.punish", "punish", {}, PunishTabRows},
    {TabId::PlayerActions, "category.playerActions", "control", {}, PlayerActionRows},
    {TabId::PlayerFun, "category.playerFun", "effects", {}, PlayerFunRows},
    // The round modifiers are `Fun::Toggles`, which every admin with this permission gets all of.
    {TabId::RoundModes, "category.roundModes", "fun", Permission::FunMode, {}},
    {TabId::MapVote, "category.mapVote", "map", {}, MapVoteRows},
    {TabId::MySettings, "category.mySettings", "chat", {}, MySettingsRows},
}};

/** The tab @p id describes. MenuCatalogTests pins @ref Tabs in enum order. */
inline constexpr const TabSpec& FindTab(TabId id)
{
    return Tabs[static_cast<std::size_t>(id)];
}

}  // namespace AdminSystem::Admin::Menu
