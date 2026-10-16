# pyright: reportAttributeAccessIssue=false, reportOptionalCall=false

import shutil
from typing import Any

from conan import ConanFile
from conan.tools.cmake import CMakeDeps, CMakeToolchain


class CS2PluginsConan(ConanFile):
    settings: Any = "os", "compiler", "build_type", "arch"

    # VoltMod supplies cpr, glaze, sqlpp23 and its connectors, s2sdk, and KHook transitively.
    requires = "voltmod/[~1.8]"

    default_options = {
        "*:shared": False,
        "openssl/*:no_apps": True,
        "openssl/*:no_fips": True,
    }

    def build_requirements(self) -> None:
        self.test_requires("doctest/2.5.2")

    def layout(self) -> None:
        # Match the build path used by voltmod and the CMake presets.
        toolchain = "windows-msvc" if self.settings.os == "Windows" else "linux-steamrt"
        build = f"build/{toolchain}-{str(self.settings.build_type).lower()}"
        self.folders.build = build
        self.folders.generators = f"{build}/generators"

    def generate(self) -> None:
        CMakeDeps(self).generate()
        toolchain = CMakeToolchain(self)
        toolchain.user_presets_path = False
        toolchain.variables["CMAKE_POSITION_INDEPENDENT_CODE"] = True
        # Via the toolchain so `cmake --preset`, `conan build` and `conan create` all get it.
        if shutil.which("ccache"):
            toolchain.variables["CMAKE_CXX_COMPILER_LAUNCHER"] = "ccache"
        toolchain.generate()
