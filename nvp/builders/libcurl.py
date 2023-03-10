"""This module provide the builder for the libcurl library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("libcurl", Builder(bman))


class Builder(NVPBuilder):
    """libcurl builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        ssl_dir = self.man.get_library_root_dir("openssl").replace("\\", "/")

        flags = [
            "-DCURL_USE_OPENSSL=ON",
            f"-DOPENSSL_ROOT_DIR={ssl_dir}",
            # f"-DOPENSSL_LIBRARIES={ssl_dir}/lib",
            f"-DOPENSSL_INCLUDE_DIR={ssl_dir}/include",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/zlib.lib",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
        ]
        self.run_cmake(build_dir, prefix, ".", flags)

        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        ssl_dir = self.man.get_library_root_dir("openssl").replace("\\", "/")
        self.append_compileflag(f"-I{ssl_dir}/include")
        self.append_linkflag(f"-L{ssl_dir}/lib64")
        self.append_linkflag("-lssl")
        self.append_linkflag("-lcrypto")

        flags = [
            "-DCURL_USE_OPENSSL=ON",
            f"-DOPENSSL_ROOT_DIR={ssl_dir}",
            # f"-DOPENSSL_LIBRARIES={ssl_dir}/lib64",
            # f"-DOPENSSL_INCLUDE_DIR={ssl_dir}/include",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/libz.a",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
        ]

        self.run_cmake(build_dir, prefix, ".", flags)

        self.run_ninja(build_dir)
