"""This module provide the builder for the libpng library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("libpng", Builder(bman))


class Builder(NVPBuilder):
    """libpng builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: will not compile with clang on windows.
        # Get zlib folder:
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")

        flags = [f"-DZLIB_INCLUDE_DIR={zlib_dir}/include"]

        if self.compiler.is_emcc():
            flags += ["-DPNG_SHARED=OFF", f"-DZLIB_LIBRARY={zlib_dir}/lib/libz.a"]
        else:
            flags += [f"-DZLIB_LIBRARY={zlib_dir}/lib/zlibstatic.lib"]

        # self.append_compileflag(f"-I{zlib_dir}/include")

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        # Get zlib folder:
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        flags = [f"-DZLIB_INCLUDE_DIR={zlib_dir}/include", f"-DZLIB_LIBRARY={zlib_dir}/lib/libz.a"]

        if self.compiler.is_emcc():
            flags += ["-DPNG_SHARED=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)

        self.run_ninja(build_dir)
