"""This module provide the builder for the proj4 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("proj4", Builder(bman))


class Builder(NVPBuilder):
    """proj4 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        sqlite_dir = self.man.get_library_root_dir("sqlite").replace("\\", "/")
        tiff_dir = self.man.get_library_root_dir("tiff").replace("\\", "/")
        curl_dir = self.man.get_library_root_dir("libcurl").replace("\\", "/")
        logger.info("Using sqlite dir: %s", sqlite_dir)

        self.prepend_env_list([self.get_path(sqlite_dir, "bin")], self.env)
        self.append_compileflag(f"-I{sqlite_dir}/include")
        # self.append_compileflag(f"-I{tiff_dir}/include")
        self.append_linkflag(f"-l{sqlite_dir}/lib/sqlite3.lib")
        # self.append_linkflag(f"-l{tiff_dir}/lib/tiff.lib")
        flags = [
            f"-DTIFF_LIBRARY={tiff_dir}/lib/tiff.lib",
            f"-DTIFF_INCLUDE_DIR={tiff_dir}/include",
            f"-DCURL_LIBRARY={curl_dir}/lib/libcurl.lib",
            f"-DCURL_INCLUDE_DIR={curl_dir}/include",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        flags = []
        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)
