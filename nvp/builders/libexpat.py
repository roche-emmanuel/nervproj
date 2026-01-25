"""This module provide the builder for the libexpat library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("libexpat", Builder(bman))


class Builder(NVPBuilder):
    """libexpat builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        flags = [
            "-S",
            "expat",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, "expat", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        flags = [
            "-S",
            "expat",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, "expat", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
