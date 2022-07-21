"""This module provide the builder for the spdlog library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('spdlog', SpdLogBuilder(bman))


class SpdLogBuilder(NVPBuilder):
    """spdlog builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for spdlog on windows"""

        flags = ["-S", ".", "-B", "build"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build method for spdlog on linux"""

        flags = ["-S", ".", "-B", "build"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
