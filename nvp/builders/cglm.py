"""This module provide the builder for the cglm library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("cglm", CglmBuilder(bman))


class CglmBuilder(NVPBuilder):
    """cglm builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for cglm on windows"""

        build_dir = self.get_path(build_dir, "release_build")
        self.make_folder(build_dir)

        flags = [
            "-DCGLM_SHARED=OFF",
            "-DCGLM_STATIC=ON",
            "-DCGLM_USE_C99=OFF",
        ]

        self.run_cmake(build_dir, prefix, "..", flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for glfw on linux"""

        build_dir = self.get_path(build_dir, "release_build")
        self.make_folder(build_dir)

        flags = [
            "-DCGLM_SHARED=OFF",
            "-DCGLM_STATIC=ON",
            "-DCGLM_USE_C99=OFF",
        ]

        self.run_cmake(build_dir, prefix, "..", flags)
        self.run_ninja(build_dir)
