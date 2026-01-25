"""This module provide the builder for the libosmium library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("libosmium", Builder(bman))


class Builder(NVPBuilder):
    """libosmium builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        bz2_dir = self.man.get_library_root_dir("bzip2").replace("\\", "/")
        bz2_lib = "libbz2.a" if self.compiler.is_emcc() else "bz2.lib"
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a" if self.compiler.is_emcc() else "zlibstatic.lib"
        pz_dir = self.man.get_library_root_dir("protozero").replace("\\", "/")
        boost_dir = self.man.get_library_root_dir("boost").replace("\\", "/")
        lz4_dir = self.man.get_library_root_dir("lz4").replace("\\", "/")
        lz4_lib = "liblz4_static.a" if self.compiler.is_emcc() else "liblz4_static.lib"
        libexpat_dir = self.man.get_library_root_dir("libexpat").replace("\\", "/")
        libexpat_lib = "libexpat.a" if self.compiler.is_emcc() else "libexpat.lib"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_TESTING=OFF",
            "-DBUILD_SHARED_LIBS=OFF",
            f"-DBZIP2_LIBRARIES={bz2_dir}/lib/{bz2_lib}",
            f"-DBZIP2_INCLUDE_DIR={bz2_dir}/include",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPROTOZERO_INCLUDE_DIR={pz_dir}/include",
            # f"-DBoost_INCLUDE_DIRS={boost_dir}/include",
            f"-DBoost_FOUND=TRUE",
            f"-DBOOST_INCLUDEDIR={boost_dir}/include",
            f"-DBOOST_LIBRARYDIR={boost_dir}/lib",
            f"-DLZ4_INCLUDE_DIR={lz4_dir}/include",
            f"-DLZ4_LIBRARY={lz4_dir}/lib/{lz4_lib}",
            f"-DEXPAT_INCLUDE_DIR={libexpat_dir}/include",
            f"-DEXPAT_LIBRARY={libexpat_dir}/lib/{libexpat_lib}",
            "-DBUILD_EXAMPLES=OFF",
            "-DBUILD_BENCHMARKS=OFF",
        ]

        if self.compiler.is_emcc():
            self.append_compileflag("-s USE_BOOST_HEADERS=1")
            self.append_linkflag("-s USE_BOOST_HEADERS=1")
            self.patch_file(
                self.get_path(build_dir, "CMakeLists.txt"), "find_package(Boost CONFIG 1.38)", "#find_package(Boost CONFIG 1.38)"
            )
            flags += [
                f"-DBoost_INCLUDE_DIRS={boost_dir}/include",
            ]
        else:
            self.patch_file(
                self.get_path(build_dir, "CMakeLists.txt"), "find_package(Boost CONFIG 1.38)", "find_package(Boost)"
            )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        bz2_dir = self.man.get_library_root_dir("bzip2").replace("\\", "/")
        bz2_lib = "libbz2.a"
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a"
        pz_dir = self.man.get_library_root_dir("protozero").replace("\\", "/")
        boost_dir = self.man.get_library_root_dir("boost").replace("\\", "/")
        lz4_dir = self.man.get_library_root_dir("lz4").replace("\\", "/")
        lz4_lib = "liblz4_static.a"
        libexpat_dir = self.man.get_library_root_dir("libexpat").replace("\\", "/")
        libexpat_lib = "libexpat.a"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_TESTING=OFF",
            "-DBUILD_SHARED_LIBS=OFF",
            f"-DBZIP2_LIBRARIES={bz2_dir}/lib/{bz2_lib}",
            f"-DBZIP2_INCLUDE_DIR={bz2_dir}/include",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPROTOZERO_INCLUDE_DIR={pz_dir}/include",
            # f"-DBoost_INCLUDE_DIRS={boost_dir}/include",
            f"-DBoost_FOUND=TRUE",
            f"-DBOOST_INCLUDEDIR={boost_dir}/include",
            f"-DBOOST_LIBRARYDIR={boost_dir}/lib",
            f"-DLZ4_INCLUDE_DIR={lz4_dir}/include",
            f"-DLZ4_LIBRARY={lz4_dir}/lib/{lz4_lib}",
            f"-DEXPAT_INCLUDE_DIR={libexpat_dir}/include",
            f"-DEXPAT_LIBRARY={libexpat_dir}/lib/{libexpat_lib}",
            "-DBUILD_EXAMPLES=OFF",
            "-DBUILD_BENCHMARKS=OFF",
        ]

        self.patch_file(
            self.get_path(build_dir, "CMakeLists.txt"), "find_package(Boost CONFIG 1.38)", "find_package(Boost)"
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
