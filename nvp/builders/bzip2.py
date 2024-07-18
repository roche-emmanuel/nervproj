"""This module provide the builder for the bzip2 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("bzip2", Builder(bman))


class Builder(NVPBuilder):
    """bzip2 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        # Create the cmake file:
        cmake_content = """cmake_minimum_required(VERSION 3.10)
project(bzip2 C)

add_library(bz2 STATIC
    blocksort.c
    bzlib.c
    compress.c
    crctable.c
    decompress.c
    huffman.c
    randtable.c
)

target_include_directories(bz2 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# Installation instructions
install(TARGETS bz2
    ARCHIVE DESTINATION lib
)

install(FILES bzlib.h
    DESTINATION include
)
"""
        self.write_text_file(cmake_content, self.get_path(build_dir, "CMakeLists.txt"))

        flags = ["-B", "release_build"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        self.multi_patch_file(
            self.get_path(build_dir, "Makefile"),
            ("CFLAGS=-Wall -Winline -O2 -g $(BIGFILES)", "CFLAGS=-Wall -Winline -O2 -g $(BIGFILES) -fPIC"),
        )

        self.exec_make(build_dir, ["libbz2.a"])

        # We manually install the files:
        self.install_files("include", r"bzlib\.h$", "include")
        self.install_files("lib", r"libbz2\.a$", "lib")
