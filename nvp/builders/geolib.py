"""This module provide the builder for the geolib library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("geolib", Builder(bman))


class Builder(NVPBuilder):
    """geolib builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: compilation seems only supported with MSVC ?
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.patch_file(self.get_path(build_dir, "CMakeLists.txt"), "include (CPack)", "#include (CPack)")
        self.patch_file(self.get_path(build_dir, "CMakeLists.txt"), "add_subdirectory (js)", "#add_subdirectory (js)")
        self.patch_file(
            self.get_path(build_dir, "CMakeLists.txt"), "add_subdirectory (matlab)", "#add_subdirectory (matlab)"
        )
        self.patch_file(
            self.get_path(build_dir, "CMakeLists.txt"),
            "add_subdirectory (python/geographiclib)",
            "#add_subdirectory (python/geographiclib)",
        )
        self.patch_file(
            self.get_path(build_dir, "CMakeLists.txt"), "add_subdirectory (examples)", "#add_subdirectory (examples)"
        )

        # git_dir = self.tools.get_tool_dir("git")
        # self.prepend_env_list([git_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF", "-DFT_REQUIRE_ZLIB=TRUE"]
        # if self.compiler.is_emcc():

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
