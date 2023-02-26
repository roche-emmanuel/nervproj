"""This module provide the builder for the nspr library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("nspr", Builder(bman))


class Builder(NVPBuilder):
    """nspr builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        raise NotImplementedError()

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        self.run_configure(build_dir, prefix, ["--enable-optimize", "--enable-64bit"])

        self.run_make(build_dir)
