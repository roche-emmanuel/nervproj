"""This module provide the builder for the libjpeg library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("libjpeg", Builder(bman))


class Builder(NVPBuilder):
    """libjpeg builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: will not build with clang on windows for now.
        flags = []
        if self.compiler.is_emcc():
            # flags = ["-DBUILD_SHARED_LIBS=OFF"]
            # "-DWITH_TURBOJPEG=OFF"
            flags = ["-DENABLE_SHARED=OFF", "-DREQUIRE_SIMD=OFF", "-DWITH_SIMD=OFF"]

        # Add NASM dir:
        nasm_dir = self.tools.get_tool_dir("nasm")
        self.prepend_env_list([nasm_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        flags = []
        if self.compiler.is_emcc():
            flags = ["-DENABLE_SHARED=OFF", "-DREQUIRE_SIMD=OFF", "-DWITH_SIMD=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)
