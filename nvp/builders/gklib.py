"""This module provide the builder for the GKlib library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("GKlib", Builder(bman))


class Builder(NVPBuilder):
    """GKlib builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DSHARED=OFF",
            "-DGKLIB_BUILD_APPS=OFF",
        ]

        cmake_file = self.get_path(build_dir, "CMakeLists.txt")
        self.patch_file(
            cmake_file,
            "add_library(${PROJECT_NAME} ${GKLIB_LIBRARY_TYPE})",
            "add_library(${PROJECT_NAME} ${GKLIB_LIBRARY_TYPE})\ninclude_directories(include/win32)",
        )

        io_file = self.get_path(build_dir, "src/io.c")
        self.patch_file(
            io_file,
            "#include <GKlib.h>",
            "#ifdef _WIN32\n#include <io.h>\n#endif\n#include <GKlib.h>",
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DSHARED=OFF",
            "-DGKLIB_BUILD_APPS=OFF",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
