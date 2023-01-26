"""This module provide the builder for the qt6 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("QT6", QT6Builder(bman))


class QT6Builder(NVPBuilder):
    """QT6 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for QT6 on windows"""

        # build_dir = self.get_path(build_dir, "src")
        logger.info("Should build QT6 here: build_dir: %s", build_dir)

        # First we write the config.opt.in file:
        self.write_text_file("", build_dir, "config.opt.in")

        # Next we call cmake to generate the config.opt file:
        cmd = [
            self.tools.get_cmake_path(),
            "-DIN_FILE=config.opt.in",
            "-DOUT_FILE=config.opt",
            "-DIGNORE_ARGS=-top-level",
            "-P",
            f"{build_dir}/qtbase/cmake/QtWriteArgsFile.cmake",
        ]

        logger.info("Cmake command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        logger.info("Done generating config.opt file.")

    # rem Write config.opt if we're not currently -redo'ing
    # if "!rargs!" == "" (
    #     echo.%*>config.opt.in
    #     cmake -DIN_FILE=config.opt.in -DOUT_FILE=config.opt -DIGNORE_ARGS=-top-level -P "%QTSRC%\cmake\QtWriteArgsFile.cmake"
    # )

    # rem Launch CMake-based configure
    # set TOP_LEVEL_ARG=
    # if %TOPLEVEL% == true set TOP_LEVEL_ARG=-DTOP_LEVEL=TRUE
    # cmake -DOPTFILE=config.opt %TOP_LEVEL_ARG% -P "%QTSRC%\cmake\QtProcessConfigureArgs.cmake"

    # flags = ["-DCMAKE_CXX_FLAGS_RELEASE=/MT", "-DSDL_STATIC=ON"]

    # self.run_cmake(build_dir, prefix, "..", flags)

    # self.run_ninja(build_dir)

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for QT6 on linux"""

        # build_dir = self.get_path(build_dir, "src")

        # logger.info("Using CXXFLAGS: %s", self.env['CXXFLAGS'])
        # logger.info("Using build env: %s", self.pretty_print(self.env))

        # flags = ["-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON"]

        # self.run_cmake(build_dir, prefix, "..", flags)

        # self.run_ninja(build_dir)
