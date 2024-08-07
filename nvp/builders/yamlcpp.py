"""This module provide the builder for the yamlcpp library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("yamlcpp", Builder(bman))


class Builder(NVPBuilder):
    """yamlcpp builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        # zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        # ssl_dir = self.man.get_library_root_dir("openssl").replace("\\", "/")

        flags = [
            "-DYAML_BUILD_SHARED_LIBS=OFF",
            # f"-DOPENSSL_ROOT_DIR={ssl_dir}",
            # # f"-DOPENSSL_LIBRARIES={ssl_dir}/lib",
            # f"-DOPENSSL_INCLUDE_DIR={ssl_dir}/include",
            # f"-DZLIB_LIBRARY={zlib_dir}/lib/zlib.lib",
            # f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
        ]
        self.run_cmake(build_dir, prefix, ".", flags=flags)

        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = [
            "-DYAML_BUILD_SHARED_LIBS=OFF",
        ]
        self.run_cmake(build_dir, prefix, ".", flags=flags)

        self.run_ninja(build_dir)
