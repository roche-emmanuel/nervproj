"""This module provide the builder for the libxml2 library."""

import logging

from nvp.components.build import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('libxml2', Builder(bman))


class Builder(NVPBuilder):
    """libxml2 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        self.run_cmake(build_dir, prefix, ".")

        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        self.run_cmake(build_dir, prefix, ".")

        self.run_ninja(build_dir)
