"""This module provide the builder for the cryptopp library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("cryptopp", Builder(bman))


class Builder(NVPBuilder):
    """cryptopp builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: compilation seems only supported with MSVC ?
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        # Note: this doesn't build with clang for now.
        
        git_dir = self.tools.get_tool_dir("git")
        self.prepend_env_list([git_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]
        # if self.compiler.is_emcc():

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
