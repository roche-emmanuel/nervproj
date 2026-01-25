"""This module provide the builder for the lz4 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("lz4", Builder(bman))

cmakefile = """cmake_minimum_required(VERSION 3.13)

project(lz4 C)

# Collect all source files
set(LZ4_SOURCES
    lz4.c
    lz4hc.c
    lz4frame.c
    lz4file.c
    xxhash.c
)

# Create static library
add_library(lz4_static STATIC ${LZ4_SOURCES})

# Ensure the output name is exactly "lz4_static.a"
set_target_properties(lz4_static PROPERTIES
    OUTPUT_NAME lz4_static
    POSITION_INDEPENDENT_CODE ON
)

# Public include directory
target_include_directories(lz4_static
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
        $<INSTALL_INTERFACE:include>
)

# Match the Makefile behavior
target_compile_definitions(lz4_static
    PRIVATE XXH_NAMESPACE=LZ4_
)

# Optional: reasonable defaults for optimization
if(NOT MSVC)
    target_compile_options(lz4_static PRIVATE -O3)
endif()

# ---- Install rules ----

install(TARGETS lz4_static
    ARCHIVE DESTINATION lib
)

install(FILES
    lz4.h
    lz4hc.h
    lz4frame.h
    lz4frame_static.h
    lz4file.h
    DESTINATION include
)
"""

class Builder(NVPBuilder):
    """lz4 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        self.write_text_file(cmakefile, build_dir, "lib", "CMakeLists.txt")
        flags = [
            "-S",
            "lib",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, "lib", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
        
    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        self.write_text_file(cmakefile, build_dir, "lib", "CMakeLists.txt")
        flags = [
            "-S",
            "lib",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, "lib", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
