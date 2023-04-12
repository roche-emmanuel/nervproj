"""This module provide the builder for the zlib library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("zlib", Builder(bman))


class Builder(NVPBuilder):
    """zlib builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        if self.compiler.is_emcc():
            # self.exec_emconfigure(build_dir, ["./configure", f"--prefix={prefix}"])
            # self.exec_emconfigure(build_dir, ["./configure"])
            # self.exec_emmake(build_dir, ["make"])
            # self.exec_emmake(build_dir, ["make", "install"])
            # em_dir = self.compiler.get_cxx_dir()
            # flags = [
            #     # f"-DCMAKE_TOOLCHAIN_FILE={em_dir}/cmake/Modules/Platform/Emscripten.cmake",
            #     # "-DBUILD_SHARED_LIBS=ON",
            # ]
            self.patch_file(
                self.get_path(build_dir, "CMakeLists.txt"),
                "set_target_properties(zlib zlibstatic PROPERTIES OUTPUT_NAME z)",
                "set_target_properties(zlibstatic PROPERTIES OUTPUT_NAME z)\nset_target_properties(zlib PROPERTIES OUTPUT_NAME zdyn)",
            )
            self.run_emcmake(build_dir, prefix, ".")
            self.run_ninja(build_dir)
            # self.run_ninja(build_dir, ["-w", "dupbuild=err"])

        else:
            self.run_cmake(build_dir, prefix, ".")
            self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        if self.compiler.is_emcc():
            self.exec_emconfigure(build_dir, ["./configure", f"--prefix={prefix}"])
            self.exec_emmake(build_dir, ["make"])
            self.exec_emmake(build_dir, ["make", "install"])
        else:
            self.run_cmake(build_dir, prefix, ".")
            self.run_ninja(build_dir)
