"""This module provide the builder for the sdl2 library."""

import logging

from nvp.components.build import BuildManager
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

        cmd = [self.tools.get_cmake_path(), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
               "-DCMAKE_CXX_FLAGS_RELEASE=/MT", "-DSDL_STATIC=ON",
               f"-DCMAKE_INSTALL_PREFIX={prefix}", ".."]
        logger.info("SDL2 build command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=self.env)

        self.execute([self.tools.get_ninja_path()], cwd=build_dir, env=self.env)
        self.execute([self.tools.get_ninja_path(), "install"], cwd=build_dir, env=self.env)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for sdl2 on linux"""

        build_dir = self.get_path(build_dir, "src")

        # logger.info("Using CXXFLAGS: %s", self.env['CXXFLAGS'])
        logger.info("Using build env: %s", self.pretty_print(self.env))

        cmd = [self.tools.get_cmake_path(), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
               "-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON", f"-DCMAKE_INSTALL_PREFIX={prefix}", ".."]

        logger.info("Executing SDL2 build command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=self.env)

        self.execute([self.tools.get_ninja_path()], cwd=build_dir, env=self.env)
        self.execute([self.tools.get_ninja_path(), "install"], cwd=build_dir, env=self.env)
