"""This module provide the builder for the secp256k1 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("secp256k1", Builder(bman))


class Builder(NVPBuilder):
    """secp256k1 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DSECP256K1_ENABLE_MODULE_ECDH=ON",
            "-DSECP256K1_ENABLE_MODULE_RECOVERY=ON",
            "-DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON",
            "-DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON",
            "-DSECP256K1_ENABLE_MODULE_MUSIG=ON",
            "-DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DSECP256K1_ENABLE_MODULE_ECDH=ON",
            "-DSECP256K1_ENABLE_MODULE_RECOVERY=ON",
            "-DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON",
            "-DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON",
            "-DSECP256K1_ENABLE_MODULE_MUSIG=ON",
            "-DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
