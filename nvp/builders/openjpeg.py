"""This module provide the builder for the openjpeg library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("openjpeg", Builder(bman))


class Builder(NVPBuilder):
    """openjpeg builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        flags = ["-DBUILD_SHARED_LIBS=OFF"]
        # if self.compiler.is_emcc():
        #     flags = ["-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        flags = ["-DBUILD_SHARED_LIBS=OFF"]
        # if self.compiler.is_emcc():
        #     flags = ["-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)
