cmake_minimum_required(VERSION 4.4)

project(cs2-plugins LANGUAGES CXX)

include(CTest)

find_package(voltmod CONFIG REQUIRED)

add_subdirectory(contracts)

add_subdirectory(plugins/admin-system)
add_subdirectory(plugins/bhop)
add_subdirectory(plugins/deathmatch)
add_subdirectory(plugins/main-menu)

# Closed source: a private submodule nobody checked out is an empty directory.
foreach(plugin anticheat stronghold)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/plugins/${plugin}/CMakeLists.txt")
        add_subdirectory("plugins/${plugin}")
    endif()
endforeach()
