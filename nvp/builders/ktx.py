"""This module provide the builder for the ktx library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("ktx", KtxBuilder(bman))


class KtxBuilder(NVPBuilder):
    """ktx builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for ktx on windows"""

        build_dir = self.get_path(build_dir, "release_build")
        self.make_folder(build_dir)

        # Need access to bash executable:
        git_dir = self.tools.get_tool_dir("git")
        self.prepend_env_list([git_dir], self.env)

        flags = [
            "-DKTX_FEATURE_STATIC_LIBRARY=ON",
            "-DKTX_FEATURE_LOADTEST_APPS=OFF",
            "-DKTX_FEATURE_TESTS=ON",
            f"-DBASH_EXECUTABLE={git_dir}/bash.exe",
        ]

        self.run_cmake(build_dir, prefix, "..", flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for glfw on linux"""

        build_dir = self.get_path(build_dir, "release_build")
        self.make_folder(build_dir)

        flags = [
            "-DKTX_FEATURE_STATIC_LIBRARY=ON",
            "-DKTX_FEATURE_LOADTEST_APPS=OFF",
            "-DKTX_FEATURE_TESTS=ON",
        ]

        self.run_cmake(build_dir, prefix, "..", flags)
        self.run_ninja(build_dir)
