"""This module provide the builder for the FastNoise2 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("FastNoise2", FastNoise2Builder(bman))


class FastNoise2Builder(NVPBuilder):
    """FastNoise2 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for FastNoise2 on windows"""

        # base_dir = self.tools.get_tool_dir('git')
        # logger.info("Using git dir: %s", base_dir)
        # pdirs = self.env.get("PATH", "")
        # self.env['PATH'] = f"{base_dir};{pdirs}"
        if self.compiler.is_emcc():
            self.append_linkflag("-S SIMD=1")

            self.multi_patch_file(
                self.get_path(build_dir, "include", "FastSIMD", "FastSIMD_Config.h"),
                (
                    "#define FASTSIMD_COMPILE_AVX512 (FASTSIMD_x86 & true )",
                    "#define FASTSIMD_COMPILE_AVX512 (FASTSIMD_x86 & false )",
                ),
                (
                    "#define FASTSIMD_COMPILE_AVX2   (FASTSIMD_x86 & true )",
                    "#define FASTSIMD_COMPILE_AVX2   (FASTSIMD_x86 & false )",
                ),
                (
                    "#define FASTSIMD_CONFIG_GENERATE_CONSTANTS false",
                    "#define FASTSIMD_CONFIG_GENERATE_CONSTANTS true",
                ),
            )
            self.multi_patch_file(
                self.get_path(build_dir, "src", "CMakeLists.txt"),
                ("-msse2", "-msimd128 -msse2"),
                ("-msse3", "-msimd128 -msse3"),
                ("-msse4.1", "-msimd128 -msse4.1"),
                ("-msse4.2", "-msimd128 -msse4.2"),
                ("-mssse3", "-msimd128 -mssse3"),
                ("-msse", "-msimd128 -msse"),
                ("-mavx2 -mfma", "-msimd128 -mavx2 -mfma"),
            )
            self.multi_patch_file(
                self.get_path(build_dir, "src", "FastSIMD", "Internal", "SSE.h"),
                (
                    "#ifdef __GNUG__",
                    "#ifdef __EMSCRIPTEN__\n#include <xmmintrin.h>\n#include <wasm_simd128.h>\n#elif defined(__GNU__)\n",
                ),
            )
            self.multi_patch_file(
                self.get_path(build_dir, "src", "FastSIMD", "FastSIMD.cpp"),
                (
                    "#ifdef __GNUG__",
                    # "#ifdef __EMSCRIPTEN__\n#include <xmmintrin.h>\n#include <wasm_simd128.h>\n#elif defined(__GNU__)\n",
                    "#ifdef __EMSCRIPTEN__\n#include <wasm_simd128.h>\n#elif defined(__GNU__)\n",
                ),
            )

        flags = ["-S", ".", "-B", "build", "-DFASTNOISE2_NOISETOOL=OFF"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build method for FastNoise2 on linux"""

        flags = ["-S", ".", "-B", "build", "-DFASTNOISE2_NOISETOOL=OFF"]
        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
