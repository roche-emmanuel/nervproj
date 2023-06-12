"""This module provide the builder for the freetype library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("freetype", Builder(bman))


class Builder(NVPBuilder):
    """freetype builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "zlibstatic.lib" if self.is_windows else "libz.a"
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        png_lib = "libpng16_static.lib" if self.is_windows else "libpng16.a"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DFT_REQUIRE_ZLIB=TRUE",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPNG_LIBRARY={png_dir}/lib/{png_lib}",
            f"-DPNG_PNG_INCLUDE_DIR={png_dir}/include",
        ]

        # if self.compiler.is_emcc():

        # nasm_dir = self.tools.get_tool_dir("nasm")
        # self.prepend_env_list([nasm_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF", "-DFT_REQUIRE_ZLIB=TRUE"]
        # if self.compiler.is_emcc():

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
