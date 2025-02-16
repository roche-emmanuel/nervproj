"""This module provide the builder for the cgal library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("cgal", Builder(bman))


class Builder(NVPBuilder):
    """cgal builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

        # # Install the files:
        # self.install_files("include", r".*", "include", recurse=True, flatten=False)
        # self.install_files("release_build/include", r".*", "include", recurse=True, flatten=False)
        # self.install_files("release_build/src", r"cgal\.a$", "lib")
        # self.install_files("release_build/src", r"cgal\.lib$", "lib")

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

        # # Install the files:
        # self.install_files("include", r".*", "include", recurse=True, flatten=False)
        # self.install_files("release_build/include", r".*", "include", recurse=True, flatten=False)
        # self.install_files("release_build/src", r"cgal\.a$", "lib")
        # self.install_files("release_build/src", r"cgal\.lib$", "lib")
