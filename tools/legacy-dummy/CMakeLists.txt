cmake_minimum_required(VERSION 4.4)

project(legacy-dummy LANGUAGES CXX)

include(FetchContent)

# Configured against the main build's Conan generators, so there is no second Conan install.
find_package(s2sdk CONFIG REQUIRED)

# Build 1411, the last Metamod before KHook: plugin API 17 and SourceHook, as the legacy plugins use.
FetchContent_Declare(metamod
    URL https://github.com/alliedmodders/metamod-source/archive/7ec0f16948ab3a0910a98b4ac10e1c0e360d5339.tar.gz
    URL_HASH SHA256=7a3af0060982bd4fe8ec4efbfe7a1e70c20c0ea60abac3de43db3fd04193035a
)
FetchContent_MakeAvailable(metamod)

add_library(legacy_dummy MODULE legacy_dummy.cpp)
target_include_directories(legacy_dummy PRIVATE
    "${metamod_SOURCE_DIR}/core"
    "${metamod_SOURCE_DIR}/core/sourcehook"
)
target_link_libraries(legacy_dummy PRIVATE VoltMod::S2SDK)
s2sdk_attach_plugin_support(legacy_dummy)

# Metamod loads addons/legacy_dummy/bin/<platform>/legacy_dummy.{dll,so}, with no lib prefix.
set_target_properties(legacy_dummy PROPERTIES
    PREFIX ""
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
)
