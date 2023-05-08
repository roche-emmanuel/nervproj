"""This module provide the builder for the dawn library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("dawn", DawnBuilder(bman))


class DawnBuilder(NVPBuilder):
    """dawn builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for dawn on windows"""

        flags = ["-DCMAKE_CXX_FLAGS_RELEASE=/MT", "-DSDL_STATIC=ON"]

        # self.run_cmake(build_dir, prefix, "..", flags)

        # self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for dawn on linux"""

        flags = ["-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON"]

        # self.run_cmake(build_dir, prefix, "..", flags)

        # self.run_ninja(build_dir)
