"""This module provide the builder for the METIS library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("METIS", Builder(bman))


class Builder(NVPBuilder):
    """METIS builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        gklib_dir = self.man.get_library_root_dir("GKlib").replace("\\", "/")

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DSHARED=OFF",
            f"-DGKLIB_PATH={gklib_dir}",
        ]

        tgt_file = self.get_path(build_dir, "include/metis.h")
        self.multi_patch_file(
            tgt_file,
            ("//#define IDXTYPEWIDTH 32", "#define IDXTYPEWIDTH 32"),
            ("//#define REALTYPEWIDTH 32", "#define REALTYPEWIDTH 32"),
        )

        tgt_file = self.get_path(build_dir, "CMakeLists.txt")
        self.multi_patch_file(
            tgt_file,
            ("set(METIS_INSTALL FALSE)", "set(METIS_INSTALL TRUE)"),
            ("include_directories(build/xinclude)", "include_directories(include)"),
            ('add_subdirectory("build/xinclude")', "add_subdirectory(include)"),
        )

        tgt_file = self.get_path(build_dir, "programs/gpmetis.c")
        self.patch_file(tgt_file, "#ifndef MACOS", "#if !defined(MACOS) && !defined(WIN32) && !defined(_WIN32)")
        tgt_file = self.get_path(build_dir, "programs/mpmetis.c")
        self.patch_file(tgt_file, "#ifndef MACOS", "#if !defined(MACOS) && !defined(WIN32) && !defined(_WIN32)")
        tgt_file = self.get_path(build_dir, "programs/ndmetis.c")
        self.patch_file(tgt_file, "#ifndef MACOS", "#if !defined(MACOS) && !defined(WIN32) && !defined(_WIN32)")

        tgt_file = self.get_path(build_dir, "programs/CMakeLists.txt")
        self.patch_file(
            tgt_file, "target_link_libraries(${prog} metis GKlib m)", "target_link_libraries(${prog} metis GKlib)"
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        gklib_dir = self.man.get_library_root_dir("GKlib").replace("\\", "/")

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DSHARED=OFF",
            f"-DGKLIB_PATH={gklib_dir}",
        ]

        tgt_file = self.get_path(build_dir, "CMakeLists.txt")
        self.multi_patch_file(
            tgt_file,
            ("include_directories(build/xinclude)", "include_directories(include)"),
            ('add_subdirectory("build/xinclude")', "add_subdirectory(include)"),
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
