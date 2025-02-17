"""This module provide the builder for the manifold library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("manifold", Builder(bman))


class Builder(NVPBuilder):
    """manifold builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        # cf . https://github.com/roche-emmanuel/manifold?tab=readme-ov-file
        clipper_dir = self.man.get_library_root_dir("clipper2").replace("\\", "/")
        # clipper_lib = "Clipper2.lib" if self.is_windows else "libClipper2.a"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DMANIFOLD_CROSS_SECTION=ON",
            "-DMANIFOLD_PYBIND=OFF",
            "-DMANIFOLD_JSBIND=OFF",
            "-DMANIFOLD_TEST=OFF",
            "-DMANIFOLD_USE_BUILTIN_CLIPPER2=OFF",
            f"-DClipper2_DIR={clipper_dir}/lib/cmake/Clipper2",
            # f"-DCLIPPER2_LIBRARY={clipper_dir}/lib/{clipper_lib}",
            # f"-DCLIPPER2_INCLUDE_DIR={clipper_dir}/include",
        ]

        # Patch used to instead the header files also on the emscripten build.
        self.patch_file(self.get_path(build_dir, "CMakeLists.txt"), "return()", "#return()")

        # git_dir = self.tools.get_tool_dir("git")
        # self.prepend_env_list([git_dir], self.env)

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
