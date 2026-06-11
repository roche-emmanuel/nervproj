"""This module provide the builder for the OpenRTI library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("OpenRTI", Builder(bman))


class Builder(NVPBuilder):
    """OpenRTI builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: this is not building with clang for now.
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "zlibstatic.lib" if self.is_windows else "libz.a"
        libexpat_dir = self.man.get_library_root_dir("libexpat").replace("\\", "/")
        libexpat_lib = "libexpat.a" if self.compiler.is_emcc() else "libexpat.lib"
        if self.compiler.is_msvc():
            libexpat_lib = "libexpatMD.lib"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DCMAKE_CXX_STANDARD=17",
            "-DCMAKE_CXX_FLAGS=/Zc:__cplusplus /EHsc",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DEXPAT_INCLUDE_DIR={libexpat_dir}/include",
            f"-DEXPAT_LIBRARY={libexpat_dir}/lib/{libexpat_lib}",
        ]

        self.patch_file(
            self.get_path(build_dir, "src/OpenRTI/CMakeLists.txt"),
            "include_directories(${EXPAT_INCLUDE_DIRS})",
            "include_directories(${EXPAT_INCLUDE_DIRS})\nadd_definitions(-DXML_STATIC)",
        )
        self.patch_file(
            self.get_path(build_dir, "include/RTI13/RTI.hh"),
            "#if __cplusplus < 201703L\n",
            "#if 0\n",
        )
        self.patch_file(
            self.get_path(build_dir, "include/RTI1516/RTI/SpecificConfig.h"),
            "#if __cplusplus < 201703L\n",
            "#if 0\n",
        )
        self.patch_file(
            self.get_path(build_dir, "include/RTI1516e/RTI/SpecificConfig.h"),
            "#if __cplusplus < 201703L\n",
            "#if 0\n",
        )
        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-S", ".", "-B", "release_build"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
