"""This module provide the builder for the freetype library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("freetype", Builder(bman))


class Builder(NVPBuilder):
    """freetype builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a" if self.compiler.is_emcc() else "zlibstatic.lib"
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        png_lib = "libpng16.a" if self.compiler.is_emcc() else "libpng16_static.lib"
        brotli_dir = self.man.get_library_root_dir("brotli").replace("\\", "/")
        brotli_lib = "brotlidec.a" if self.compiler.is_emcc() else "brotlidec.lib"
        harfbuzz_dir = self.man.get_library_root_dir("harfbuzz").replace("\\", "/")
        harfbuzz_lib = "harfbuzz.a" if self.compiler.is_emcc() else "harfbuzz.lib"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DFT_REQUIRE_ZLIB=TRUE",
            "-DFT_REQUIRE_PNG=TRUE",
            "-DFT_REQUIRE_BROTLI=TRUE",
            "-DFT_REQUIRE_HARFBUZZ=TRUE",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPNG_LIBRARY={png_dir}/lib/{png_lib}",
            f"-DPNG_PNG_INCLUDE_DIR={png_dir}/include",
            f"-DBROTLIDEC_LIBRARIES={brotli_dir}/lib/{brotli_lib}",
            f"-DBROTLIDEC_INCLUDE_DIRS={brotli_dir}/include",
            f"-DHarfBuzz_LIBRARY={harfbuzz_dir}/lib/{harfbuzz_lib}",
            f"-DHarfBuzz_INCLUDE_DIR={harfbuzz_dir}/include/harfbuzz",
        ]

        # if self.compiler.is_emcc():

        # nasm_dir = self.tools.get_tool_dir("nasm")
        # self.prepend_env_list([nasm_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a"
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        png_lib = "libpng16.a"
        brotli_dir = self.man.get_library_root_dir("brotli").replace("\\", "/")
        brotli_lib = "brotlidec.a"
        harfbuzz_dir = self.man.get_library_root_dir("harfbuzz").replace("\\", "/")
        harfbuzz_lib = "harfbuzz.a"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DFT_REQUIRE_ZLIB=TRUE",
            "-DFT_REQUIRE_PNG=TRUE",
            "-DFT_REQUIRE_BROTLI=TRUE",
            "-DFT_REQUIRE_HARFBUZZ=TRUE",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPNG_LIBRARY={png_dir}/lib/{png_lib}",
            f"-DPNG_PNG_INCLUDE_DIR={png_dir}/include",
            f"-DBROTLIDEC_LIBRARIES={brotli_dir}/lib/{brotli_lib}",
            f"-DBROTLIDEC_INCLUDE_DIRS={brotli_dir}/include",
            f"-DHarfBuzz_LIBRARY={harfbuzz_dir}/lib/{harfbuzz_lib}",
            f"-DHarfBuzz_INCLUDE_DIR={harfbuzz_dir}/include/harfbuzz",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
