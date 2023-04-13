"""This module provide the builder for the zlib library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("zlib", Builder(bman))


class Builder(NVPBuilder):
    """zlib builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        if self.compiler.is_emcc():
            self.run_cmake(build_dir, prefix, ".", generator="MinGW Makefiles")
            self.run_make(build_dir)
        else:
            self.run_cmake(build_dir, prefix, ".")
            self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        if self.compiler.is_emcc():
            self.run_cmake(build_dir, prefix, ".", generator="Unix Makefiles")
            self.run_make(build_dir)
        else:
            self.run_cmake(build_dir, prefix, ".")
            self.run_ninja(build_dir)
