"""This module provide the builder for the sdl2 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('SDL2', SDL2Builder(bman))


class SDL2Builder(NVPBuilder):
    """SDL2 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for SDL2 on windows"""

        build_dir = self.get_path(build_dir, "src")

        flags = ["-DCMAKE_CXX_FLAGS_RELEASE=/MT", "-DSDL_STATIC=ON"]

        self.run_cmake(build_dir, prefix, "..", flags)

        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for sdl2 on linux"""

        build_dir = self.get_path(build_dir, "src")

        # logger.info("Using CXXFLAGS: %s", self.env['CXXFLAGS'])
        # logger.info("Using build env: %s", self.pretty_print(self.env))

        flags = ["-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON"]

        self.run_cmake(build_dir, prefix, "..", flags)

        self.run_ninja(build_dir)
