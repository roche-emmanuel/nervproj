"""This module provide the builder for the qt6 library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("QT6", QT6Builder(bman))


# Note: on windows we also need to patch the "file_io.py" file used to generate some bindings when compiling blink,
# Because otherwise it will error trying to write too long file names, for instance:

# D:/Projects/NervProj/.pyenvs/qt6_env/python.exe ../../../3rdparty/chromium/third_party/blink/renderer/bindings/scripts/generate_bindings.py --web_idl_database gen/third_party/blink/renderer/bindings/web_idl_database.pickle --root_src_dir ../../../3rdparty/chromium/ --root_gen_dir gen --output_reldir core=third_party/blink/renderer/bindings/core/v8/ --output_reldir modules=third_party/blink/renderer/bindings/modules/v8/ enumeration callback_function callback_interface dictionary interface namespace observable_array typedef union
# multiprocessing.pool.RemoteTraceback:

# """

# Traceback (most recent call last):

#   File "D:\Projects\NervProj\.pyenvs\qt6_env\lib\multiprocessing\pool.py", line 125, in worker

#     result = (True, func(*args, **kwds))

#   File "D:\Projects\NervProj\libraries\build\QT6-6.4.2\qtwebengine\src\3rdparty\chromium\third_party\blink\renderer\bindings\scripts\bind_gen\union.py", line 1101, in generate_union

#     write_code_node_to_file(header_node, path_manager.gen_path_to(header_path))

#   File "D:\Projects\NervProj\libraries\build\QT6-6.4.2\qtwebengine\src\3rdparty\chromium\third_party\blink\renderer\bindings\scripts\bind_gen\codegen_utils.py", line 207, in write_code_node_to_file

#     web_idl.file_io.write_to_file_if_changed(

#   File "D:\Projects\NervProj\libraries\build\QT6-6.4.2\qtwebengine\src\3rdparty\chromium\third_party\blink\renderer\bindings\scripts\web_idl\file_io.py", line 45, in write_to_file_if_changed

#     with open(filepath, 'wb') as file_obj:

# FileNotFoundError: [Errno 2] No such file or directory: 'D:\\Projects\\NervProj\\libraries\\build\\QT6-6.4.2\\qtwebengine\\src\\core\\Release\\AMD64\\gen\\third_party\\blink\\renderer\\bindings\\modules\\v8\\v8_union_gpucanvascontext_imagebitmaprenderingcontext_offscreencanvasrenderingcontext2d_webgl2renderingcontext_webglrenderingcontext.h'

# """

file_io = '''
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import pickle


def read_pickle_file(filepath):
    """
    Reads the content of the file as a pickled object.
    """
    with open(filepath, 'rb') as file_obj:
        return pickle.load(file_obj)


def write_pickle_file_if_changed(filepath, obj):
    """
    Writes the given object out to |filepath| if the content changed.

    Returns True if the object is written to the file, and False if skipped.
    """
    return write_to_file_if_changed(filepath, pickle.dumps(obj))


def write_to_file_if_changed(filepath, contents):
    """
    Writes the given contents out to |filepath| if the contents changed.

    Returns True if the data is written to the file, and False if skipped.
    """

    # get the current cwd:
    prev_dir = os.getcwd()

    # get the folder of the filepath:
    folder = os.path.dirname(filepath)
    filepath = os.path.basename(filepath)
    
    # Build the folder if needed:
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Change location to the parent directory:
    os.chdir(folder)

    try:
        with open(filepath, 'rb') as file_obj:
            old_contents = file_obj.read()
    except (OSError, EnvironmentError):
        pass
    else:
        if contents == old_contents:
            # restore previous directory:
            os.chdir(prev_dir)
            return False
        os.remove(filepath)

    with open(filepath, 'wb') as file_obj:
        file_obj.write(contents)

    # restore previous directory:
    os.chdir(prev_dir)

    return True
'''


class QT6Builder(NVPBuilder):
    """QT6 builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for QT6 on windows"""

        # build_dir = self.get_path(build_dir, "src")
        logger.info("Should build QT6 here: build_dir: %s", build_dir)

        # First we write the config.opt.in file:
        self.write_text_file(
            f"-top-level -prefix {prefix} -release -optimize-size -- -DCMAKE_SUPPRESS_DEVELOPER_WARNINGS=1",
            build_dir,
            "config.opt.in",
        )

        # Next we call cmake to generate the config.opt file:
        cmd = [
            self.tools.get_cmake_path(),
            "-DIN_FILE=config.opt.in",
            "-DOUT_FILE=config.opt",
            "-DIGNORE_ARGS=-top-level",
            "-P",
            f"{build_dir}/qtbase/cmake/QtWriteArgsFile.cmake",
        ]

        # logger.info("Cmake command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        logger.info("Done generating config.opt file.")

        # prepare the python env:
        pyenv = self.ctx.get_component("pyenvs")
        pdesc = {"inherit": "default_env", "packages": ["html5lib"]}

        pyenv.add_py_env_desc("qt6_env", pdesc)

        pyenv.setup_py_env("qt6_env")
        py_dir = pyenv.get_py_env_dir("qt6_env")
        py_dir = self.get_path(py_dir, "qt6_env")

        # Prepare a nodejs env:
        nodejs = self.ctx.get_component("nodejs")

        nodejs_dir = self.get_path(build_dir, "qt6_env")
        ndesc = {"nodejs_version": "18.13.0", "packages": [], "install_dir": build_dir}

        nodejs.setup_nodejs_env("qt6_env", env_dir=build_dir, desc=ndesc, update_npm=True)

        # let's run the configure.bat file:
        perl_dir = self.tools.get_tool_root_dir("perl")
        gperf_dir = self.tools.get_tool_dir("gperf")
        bison_dir = self.tools.get_tool_dir("bison")
        flex_dir = self.tools.get_tool_dir("flex")

        # py_dir = self.get_parent_folder(self.tools.get_tool_path("python"))

        dirs = [
            self.get_path(build_dir, "qtbase", "bin"),
            py_dir,
            nodejs_dir,
            gperf_dir,
            bison_dir,
            flex_dir,
            self.get_path(perl_dir, "perl", "site", "bin"),
            self.get_path(perl_dir, "perl", "bin"),
            self.get_path(perl_dir, "c", "bin"),
        ]
        logger.info("Adding additional paths: %s", dirs)

        self.env = self.append_env_list(dirs, self.env)

        logger.info("Environment paths: %s", self.env["PATH"])

        # Apply the required patches:
        file_io_fname = f"{build_dir}/qtwebengine/src/3rdparty/chromium/third_party/blink/renderer/bindings/scripts/web_idl/file_io.py"
        self.write_text_file(file_io, file_io_fname)

        cmd = [
            self.tools.get_cmake_path(),
            "-DOPTFILE=config.opt",
            "-DTOP_LEVEL=TRUE",
            "-P",
            f"{build_dir}/qtbase/cmake/QtProcessConfigureArgs.cmake",
            "-Wno-dev",
        ]

        self.check_execute(cmd, cwd=build_dir, env=self.env)

        cmd = [self.tools.get_cmake_path(), "--build", ".", "--parallel"]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        cmd = [self.tools.get_cmake_path(), "--install", "."]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        pyenv.remove_py_env("qt6_env")

        # self.check_execute(["cmd", "/c", "configure.bat", "-prefix", prefix, "-Wno-dev"], cwd=build_dir, env=self.env)

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