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
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
        ]

        if self.compiler.is_emcc():
            flags += [
                f"-DOPENSSL_CRYPTO_LIBRARY={ssl_dir}/libx32/libcrypto.a",
                f"-DOPENSSL_SSL_LIBRARY={ssl_dir}/libx32/libssl.a",
                f"-DZLIB_LIBRARY={zlib_dir}/lib/libz.a",
            ]
        else:
            flags += [
                f"-DZLIB_LIBRARY={zlib_dir}/lib/zlib.lib",
            ]

        self.run_cmake(build_dir, prefix, ".", flags)

        self.run_ninja(build_dir)

        imp_file = self.get_path(prefix, "lib", "libcurl_imp.lib")
        if self.file_exists(imp_file):
            # If building with msvc we need to rename the lib file from "libcurl_imp.lib"
            self.rename_file(imp_file, self.get_path(prefix, "lib", "libcurl.lib"))

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        ssl_dir = self.man.get_library_root_dir("openssl").replace("\\", "/")
        self.append_compileflag(f"-I{ssl_dir}/include")
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

        if self.compiler.is_emcc():
            flags += [
                f"-DOPENSSL_CRYPTO_LIBRARY={ssl_dir}/libx32/libcrypto.a",
                f"-DOPENSSL_SSL_LIBRARY={ssl_dir}/libx32/libssl.a",
            ]
            self.append_linkflag(f"-L{ssl_dir}/libx32")
        else:
            self.append_linkflag(f"-L{ssl_dir}/lib64")

        self.run_cmake(build_dir, prefix, ".", flags)

        self.run_ninja(build_dir)
