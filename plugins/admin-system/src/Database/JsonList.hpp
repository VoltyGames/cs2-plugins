#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace AdminSystem::Database
{

/** Parse a JSON array of strings (admins.permissions, admin_groups.inherits). Empty text is an empty
 *  list; malformed text is nullopt so the caller can name the row it came from. */
std::optional<std::vector<std::string>> ReadJsonList(std::string_view text);

}  // namespace AdminSystem::Database
