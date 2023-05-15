"""This module provide the builder for the hdf4 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("hdf4", Builder(bman))


class Builder(NVPBuilder):
    """hdf4 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: building is not supported with clang here.

        # Get zlib folder:
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "zlibstatic.lib"
        jpeg_dir = self.man.get_library_root_dir("libjpeg").replace("\\", "/")

        # self.append_compileflag(f"-I{jpeg_dir}/include/openjpeg-2.5")
        # self.append_linkflag(f"-l{jpeg_dir}/lib/openjp2.lib")

        # self.patch_file(self.get_path(build_dir, "hdf/src/dfjpeg.c"), '#include "jpeglib.h"', '#include "openjpeg.h"')
        # self.patch_file(self.get_path(build_dir, "hdf/src/dfjpeg.c"), '#include "jerror.h"', '//#include "jerror.h"')

        flags = [
            "-S",
            ".",
            "-B",
            "build",
            f"-DZLIB_LIBRARY:FILEPATH={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR:PATH={zlib_dir}/include",
            # f"-DJPEG_INCLUDE_DIR:PATH={jpeg_dir}/include/openjpeg-2.5",
            f"-DJPEG_INCLUDE_DIR:PATH={jpeg_dir}/include",
            # f"-DJPEG_LIBRARY:PATH={jpeg_dir}/lib/openjp2.lib",
            f"-DJPEG_LIBRARY:PATH={jpeg_dir}/lib/jpeg-static.lib",
            "-DBUILD_STATIC_LIBS=OFF",
            "-DHDF4_PACKAGE_EXTLIBS=ON",
        ]

        # Note: we also need bash on the path:
        git_path = self.tools.get_tool_path("git")
        git_dir = self.get_parent_folder(git_path)
        self.env = self.prepend_env_list([git_dir], self.env)

        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        # Get zlib folder:
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a"

        flags = [
            "-S",
            ".",
            "-B",
            "build",
            f"-DZLIB_LIBRARY:FILEPATH={zlib_dir}/lib/{z_lib}",
            "-DZLIB_INCLUDE_DIR:PATH={zlib_dir}/include",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
