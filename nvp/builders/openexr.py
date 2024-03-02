"""This module provide the builder for the openexr library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("openexr", Builder(bman))


class Builder(NVPBuilder):
    """openexr builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        flags = ["-DBUILD_SHARED_LIBS=OFF"]

        # Note: will not build with clang on windows for now due to intrinsic
        # tried with -DCMAKE_CXX_FLAGS="-msimd128 -mssse3 -msse4.1 -msse4.2" but this doesn't work.

        # Note2: This works just fine with the EMSCRIPTEN compiler.

        # We need git on the path:
        git_dir = self.tools.get_tool_dir("git")
        self.prepend_env_list([git_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)
