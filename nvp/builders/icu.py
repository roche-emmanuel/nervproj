"""This module provide the builder for the icu library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("icu", Builder(bman))


class Builder(NVPBuilder):
    """icu builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: build not supported yet on windows.

        flags = ["-DBUILD_SHARED_LIBS=OFF"]
        # flags = ["-DSSE=ON", "-DSTATIC=ON"]
        # if self.compiler.is_emcc():

        # # Add NASM dir:
        # nasm_dir = self.tools.get_tool_dir("nasm")
        # self.prepend_env_list([nasm_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        # The build dir should be changed to "source":
        build_dir = self.get_path(build_dir, "source")

        self.run_configure(build_dir, prefix, ["--enable-static", "--disable-shared"])
        self.run_make(build_dir)
