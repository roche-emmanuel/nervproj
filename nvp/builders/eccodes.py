"""This module provide the builder for the eccodes library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("eccodes", Builder(bman))


class Builder(NVPBuilder):
    """eccodes builder class."""

    def get_flags(self):
        """Retrieve the build flags"""
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "zlibstatic.lib" if self.is_windows else "libz.a"
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        png_lib = "libpng16_static.lib" if self.is_windows else "libpng16.a"
        jpeg_dir = self.man.get_library_root_dir("openjpeg").replace("\\", "/")

        flags = [
            "-S",
            ".",
            "-B",
            "build",
            "-DBUILD_SHARED_LIBS=ON",
            "-DENABLE_NETCDF=OFF",
            "-DENABLE_PYTHON=OFF",
            "-DENABLE_JPG=ON",
            "-DENABLE_PNG=ON",
            "-DENABLE_FORTRAN=OFF",
            "-DENABLE_AEC=OFF",
            "-DENABLE_EXAMPLES=OFF",
            "-DENABLE_MEMFS=OFF",
            "-DENABLE_TESTS=OFF",
            "-DENABLE_EXTRA_TESTS=OFF",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPNG_LIBRARY={png_dir}/lib/{png_lib}",
            f"-DPNG_PNG_INCLUDE_DIR={png_dir}/include",
            f"-DOPENJPEG_INCLUDE_DIR={jpeg_dir}/include/openjpeg-2.5",
        ]

        return flags

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: did not try to build with clang.

        # Note: we also need bash on the path:
        git_path = self.tools.get_tool_path("git")
        git_dir = self.get_parent_folder(git_path)
        self.env = self.prepend_env_list([git_dir], self.env)

        tgt_file = f"{build_dir}/src/grib_api_internal.h"
        self.patch_file(
            tgt_file,
            "  #define _CRT_SECURE_NO_WARNINGS",
            "#ifndef _CRT_SECURE_NO_WARNINGS\n#define _CRT_SECURE_NO_WARNINGS\n#endif",
        )
        self.patch_file(
            tgt_file,
            "  #define _CRT_NONSTDC_NO_DEPRECATE",
            "#ifndef _CRT_NONSTDC_NO_DEPRECATE\n#define _CRT_NONSTDC_NO_DEPRECATE\n#endif",
        )

        # self.run_cmake(build_dir, prefix, flags=flags)
        flags = self.get_flags()
        self.run_cmake(build_dir, prefix, flags=flags, generator="NMake Makefiles")
        sub_dir = self.get_path(build_dir, "build")
        # self.run_ninja(sub_dir)
        self.exec_nmake(sub_dir)
        self.exec_nmake(sub_dir, ["install"])

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = self.get_flags()
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
