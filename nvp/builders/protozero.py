"""This module provide the builder for the protozero library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("protozero", Builder(bman))


class Builder(NVPBuilder):
    """protozero builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DWERROR=OFF", #Avoid error with clang.
        ]

        self.patch_file(
            self.get_path(build_dir, "tools/CMakeLists.txt"), "if(NOT MSVC)", "if(NOT WIN32)"
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
