"""This module provide the builder for the FastNoise2 library."""

import logging

from nvp.components.build import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('FastNoise2', FastNoise2Builder(bman))


class FastNoise2Builder(NVPBuilder):
    """FastNoise2 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for FastNoise2 on windows"""

        # base_dir = self.tools.get_tool_dir('git')
        # logger.info("Using git dir: %s", base_dir)
        # pdirs = self.env.get("PATH", "")
        # self.env['PATH'] = f"{base_dir};{pdirs}"

        flags = ["-S", ".", "-B", "build", "-DFASTNOISE2_NOISETOOL=OFF"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build method for FastNoise2 on linux"""

        flags = ["-S", ".", "-B", "build", "-DFASTNOISE2_NOISETOOL=OFF"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
