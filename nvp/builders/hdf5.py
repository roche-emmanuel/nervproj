"""This module provide the builder for the hdf5 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("hdf5", Builder(bman))


class Builder(NVPBuilder):
    """hdf5 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: building is not supported with clang here.

        # Get zlib folder:
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "zlibstatic.lib"

        flags = [
            "-S",
            ".",
            "-B",
            "build",
            f"-DZLIB_LIBRARY:FILEPATH={zlib_dir}/lib/{z_lib}",
            "-DZLIB_INCLUDE_DIR:PATH={zlib_dir}/include",
        ]

        # Note: we also need bash on the path:
        git_path = self.tools.get_tool_path("git")
        git_dir = self.get_parent_folder(git_path)
        self.env = self.prepend_env_list([git_dir], self.env)

        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        # Get zlib folder:
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a"

        flags = [
            "-S",
            ".",
            "-B",
            "build",
            f"-DZLIB_LIBRARY:FILEPATH={zlib_dir}/lib/{z_lib}",
            "-DZLIB_INCLUDE_DIR:PATH={zlib_dir}/include",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)
        sub_dir = self.get_path(build_dir, "build")
        self.run_ninja(sub_dir)
