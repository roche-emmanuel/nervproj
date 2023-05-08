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

        # Bootstrap the gclient configuration
        # cp scripts/standalone.gclient .gclient
        self.copy_file(self.get_path(build_dir, "scripts", "standalone.gclient"), self.get_path(build_dir, ".gclient"))

        gclient_path = self.tools.get_tool_path("gclient")

        # Should also add the depot_tools folder in the PATH:
        depot_dir = self.tools.get_tool_dir("gclient")
        self.prepend_env_list([depot_dir], self.env)

        # Fetch external dependencies and toolchains with gclient
        # gclient sync
        cmd = [gclient_path, "sync"]
        self.execute(cmd, cwd=build_dir)

        # Run cmake:
        flags = ["-S", ".", "-B", "release_build"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for dawn on linux"""

        flags = ["-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON"]

        # self.run_cmake(build_dir, prefix, "..", flags)

        # self.run_ninja(build_dir)
