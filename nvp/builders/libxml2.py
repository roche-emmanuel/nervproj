"""This module provide the builder for the libxml2 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("libxml2", Builder(bman))


class Builder(NVPBuilder):
    """libxml2 builder class."""

    def get_cmake_flags(self):
        """Retrive the applicable cmake flags for the build"""

        # get the iconv library dir:
        iconv_dir = self.man.get_library_root_dir("libiconv")
        zlib_dir = self.man.get_library_root_dir("zlib")

        z_lib = "zlibstatic.lib" if self.is_windows else "libz.a"
        iconv_lib = "libiconvStatic.lib" if self.is_windows else "libiconv.a"

        return [
            f"-DIconv_LIBRARY={iconv_dir}/lib/{iconv_lib}",
            f"-DIconv_INCLUDE_DIR={iconv_dir}/include",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            "-DLIBXML2_WITH_LZMA=OFF",
            "-DLIBXML2_WITH_PYTHON=OFF",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        flags = self.get_cmake_flags()
        self.run_cmake(build_dir, prefix, ".", flags)

        self.run_ninja(build_dir)

        if self.compiler.is_clang():
            # Add the s suffix to the library:
            srcfile = self.get_path(prefix, "lib", "libxml2.lib")
            dstfile = self.get_path(prefix, "lib", "libxml2s.lib")
            self.move_path(srcfile, dstfile)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = self.get_cmake_flags()
        self.run_cmake(build_dir, prefix, ".", flags)

        self.run_ninja(build_dir)
