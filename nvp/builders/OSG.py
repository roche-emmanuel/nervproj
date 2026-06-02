"""This module provide the builder for the OSG library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("OSG", Builder(bman))


class Builder(NVPBuilder):
    """OSG builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a" if self.compiler.is_emcc() else "zlibstatic.lib"
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        png_lib = "libpng16.a" if self.compiler.is_emcc() else "libpng16_static.lib"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DOPENGL_PROFILE=GL3",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPNG_LIBRARY={png_dir}/lib/{png_lib}",
            f"-DPNG_PNG_INCLUDE_DIR={png_dir}/include",
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
            "-DOPENGL_PROFILE=GL3",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
