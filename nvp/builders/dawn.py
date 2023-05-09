"""This module provide the builder for the dawn library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("dawn", DawnBuilder(bman))


class DawnBuilder(NVPBuilder):
    """dawn builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for dawn on windows"""

        # Bootstrap the gclient configuration
        # cp scripts/standalone.gclient .gclient
        logger.info("Copying gclient config...")
        self.copy_file(self.get_path(build_dir, "scripts", "standalone.gclient"), self.get_path(build_dir, ".gclient"))

        gclient_path = self.tools.get_tool_path("gclient")

        # Should also add the depot_tools folder in the PATH:
        # Also add path to powershell:
        depot_dir = self.tools.get_tool_dir("gclient")
        paths = [depot_dir, "C:\\Windows\\System32\\WindowsPowerShell\\v1.0"]
        self.prepend_env_list(paths, self.env)

        # Force adding ninja path on top:
        ninja_dir = self.tools.get_tool_dir("ninja")
        self.env["PATH"] = ninja_dir + ";" + self.env["PATH"]

        # Need the following define on windows to avoid an issue:
        # cf. https://chromium.googlesource.com/chromium/src/+/HEAD/docs/windows_build_instructions.md
        self.env["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"

        # Fetch external dependencies and toolchains with gclient
        # gclient sync
        cmd = [gclient_path, "sync"]
        logger.info("Executing gclient sync...")
        self.execute(cmd, cwd=build_dir, env=self.env)

        # Run cmake:
        logger.info("Executing cmake...")
        # Need to add python executable path:
        py_path = self.tools.get_tool_path("python")
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            f"-DPYTHON_EXECUTABLE={py_path}",
            f"-DPython_EXECUTABLE={py_path}",
            "-DDAWN_ENABLE_PIC=ON",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)

        logger.info("Executing ninja...")
        sub_dir = self.get_path(build_dir, "release_build")
        # self.run_ninja(sub_dir)
        self.exec_ninja(sub_dir)

        # logger.info("Installing dawn libraries...")
        # lib_dir = self.get_path(prefix, "lib")
        # self.make_folder(lib_dir)
        # libs = [""]
        # # self.copy_file()

        logger.info("Danw build done.")

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for dawn on linux"""

        flags = ["-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON"]

        # self.run_cmake(build_dir, prefix, "..", flags)

        # self.run_ninja(build_dir)
