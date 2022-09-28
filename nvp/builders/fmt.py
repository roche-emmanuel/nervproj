"""This module provide the builder for the fmt library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("fmt", FmtBuilder(bman))


class FmtBuilder(NVPBuilder):
    """Fmt builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for Fmt on windows"""

        flags = ["-S", ".", "-B", "build", "-DBUILD_SHARED_LIBS=FALSE", "-DCMAKE_POSITION_INDEPENDENT_CODE=TRUE"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build method for Fmt on linux"""

        flags = ["-S", ".", "-B", "build", "-DBUILD_SHARED_LIBS=FALSE", "-DCMAKE_POSITION_INDEPENDENT_CODE=TRUE"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
