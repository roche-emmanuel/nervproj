"""This module provide the builder for the manifold library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("manifold", Builder(bman))


class Builder(NVPBuilder):
    """manifold builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        # cf . https://github.com/roche-emmanuel/manifold?tab=readme-ov-file
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DMANIFOLD_CROSS_SECTION=OFF",
            "-DMANIFOLD_PYBIND=OFF",
            "-DMANIFOLD_TEST=OFF",
            # "-DMANIFOLD_USE_BUILTIN_CLIPPER2=ON",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
