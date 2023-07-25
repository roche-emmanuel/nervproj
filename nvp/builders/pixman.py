"""This module provide the builder for the pixman library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("pixman", Builder(bman))


class Builder(NVPBuilder):
    """pixman builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Only applicable to msvc
        self.check(self.compiler.is_msvc(), "Only available wit MSVC compiler")

        # Reference:
        # cd pixman
        # sed s/-MD/-MT/ Makefile.win32.common > Makefile.win32.common.fixed
        # mv Makefile.win32.common.fixed Makefile.win32.common
        # if [ $MSVC_PLATFORM_NAME = x64 ]; then
        #     # pass -B for switching between x86/x64
        #     make pixman -B -f Makefile.win32 "CFG=release" "MMX=off"
        # else
        #     make pixman -B -f Makefile.win32 "CFG=release"
        # fi
        # cd ..

        # Path the Makefile.win32.common file:
        self.patch_file(self.get_path(build_dir, "Makefile.win32.common"), "MD", "MT")

        # Run the make command:
        flags = ["pixman", "-B", "-f", "Makefile.win32", "CFG=release", "MMX=off"]
        self.exec_make(build_dir, flags)

        # Manually install the files:
        inc_dir = self.get_path(prefix, "include")
        self.make_folder(inc_dir)
        self.copy_file(self.get_path(build_dir, "pixman/pixman-version.h"), self.get_path(inc_dir, "pixman-version.h"))
        self.copy_file(self.get_path(build_dir, "pixman/pixman.h"), self.get_path(inc_dir, "pixman.h"))
        lib_dir = self.get_path(prefix, "lib")
        self.make_folder(lib_dir)
        self.copy_file(self.get_path(build_dir, "pixman/release/pixman-1.lib"), self.get_path(lib_dir, "pixman-1.lib"))

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF", "-DFT_REQUIRE_ZLIB=TRUE"]
        # if self.compiler.is_emcc():

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
