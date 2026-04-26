"""This module provide the builder for the lua library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("lua", Builder(bman))


class Builder(NVPBuilder):
    """lua builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # NOTE: doesn't compile with clang on windows
        # And it doesn't compile with emscripten either
        git_path = self.tools.get_tool_path("git")
        git_dir = self.get_parent_folder(git_path)
        self.env = self.prepend_env_list([git_dir], self.env)

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
