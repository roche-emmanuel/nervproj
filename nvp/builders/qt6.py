"""This module provide the builder for the qt6 library."""

# See this page for target emscripten versions: https://doc.qt.io/qt-6/wasm.html
# Qt 6.2: 2.0.14
# Qt 6.3: 3.0.0
# Qt 6.4: 3.1.14
# Qt 6.5: 3.1.25
# Qt 6.6: 3.1.37
# Qt 6.7: 3.1.50

# To install we need for instance:
# nvp emsdk install 3.1.50
# nvp emsdk activate 3.1.50

# Note: Can build QT6.4 with emscripten **3.1.35**
# But now updating to version **3.1.64**

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("QT6", QT6Builder(bman))
    bman.register_builder("QT6_7", QT6Builder(bman))


# Note: on windows we really need to build from some disk "root location"
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

# So below we move the build location from "D:\\Projects\\NervProj\\libraries\\build\\QT6-6.4.2" to
# just "D:\\QT" (for instance)


class QT6Builder(NVPBuilder):
    """QT6 builder class."""

    def generate_qt_config(self, build_dir, prefix, args, cmake_args):
        """Helper function used to generate the QT config.opt file"""
        self.write_text_file(
            f"-top-level -prefix {prefix} -release {args} -- {cmake_args}",
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

        logger.info("Gen config command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)
        logger.info("Done generating config.opt file.")

    def build_with_emcc_win(self, build_dir, prefix, _desc):
        """Build with emcc on windows"""
        # Building with emcc:

        # get the host path for QT:
        host_path = prefix.replace("windows_emcc", "windows_clang")
        logger.info("QT host path is: %s", host_path)
        self.check(self.dir_exists(host_path), "QT host path must exists.")

        # self.env["QT_HOST_PATH"]=host_path
        args = f"-qt-host-path {host_path} -platform wasm-emscripten -opensource"
        args += " -confirm-license -no-warnings-are-errors -feature-thread -static"
        args += " -skip qtwebengine -skip qtquick3d -skip qtquick3dphysics"

        em_dir = self.compiler.get_cxx_dir()
        cmake_args = f"-DCMAKE_TOOLCHAIN_FILE={em_dir}/cmake/Modules/Platform/Emscripten.cmake -DCMAKE_SUPPRESS_DEVELOPER_WARNINGS=1"
        self.generate_qt_config(build_dir, prefix, args, cmake_args)

        cmd = [
            self.tools.get_cmake_path(),
            "-DOPTFILE=config.opt",
            "-DTOP_LEVEL=TRUE",
            "-P",
            f"{build_dir}/qtbase/cmake/QtProcessConfigureArgs.cmake",
            "-Wno-dev",
        ]

        # let's run the configure.bat file:
        perl_dir = self.tools.get_tool_root_dir("perl")
        gperf_dir = self.tools.get_tool_dir("gperf")
        bison_dir = self.tools.get_tool_dir("bison")
        flex_dir = self.tools.get_tool_dir("flex")

        # py_dir = self.get_parent_folder(self.tools.get_tool_path("python"))

        dirs = [
            self.get_path(build_dir, "qtbase", "bin"),
            # py_dir,
            # nodejs_dir,
            gperf_dir,
            bison_dir,
            flex_dir,
            self.get_path(perl_dir, "perl", "site", "bin"),
            self.get_path(perl_dir, "perl", "bin"),
            self.get_path(perl_dir, "c", "bin"),
        ]
        logger.info("Adding additional paths: %s", dirs)

        self.env = self.append_env_list(dirs, self.env)

        logger.info("Post config command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        # Building the library now:
        logger.info("Building QT6 libraries...")
        # cmd = [self.tools.get_cmake_path(), "--build", ".", "-t", "qtbase", "-t", "qtdeclarative"]
        cmd = [self.tools.get_cmake_path(), "--build", ".", "--parallel"]
        logger.info("cmake command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        logger.info("Installing QT6 libraries...")
        cmd = [self.tools.get_cmake_path(), "--install", "."]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        logger.info("Done building QT6 with emcc.")
        return

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for QT6 on windows"""

        if self.compiler.is_emcc():
            return self.build_with_emcc_win(build_dir, prefix, _desc)

        # build_dir = self.get_path(build_dir, "src")
        # logger.info("Should build QT6 here: build_dir: %s", build_dir)
        # We need to move the build dir at the root of the filesystem:
        prev_build_dir = build_dir
        build_dir = build_dir[:3] + "QT"

        # Remove the previous out build folder if needed:
        if self.dir_exists(build_dir):
            logger.info("Removing base disk QT build folder %s", build_dir)
            self.remove_folder(build_dir, recursive=True)

        if not self.dir_exists(build_dir):
            logger.info("QT6 using base filesystem build_dir: %s", build_dir)
            self.rename_folder(prev_build_dir, build_dir)

            # First we write the config.opt.in file:
            # cf. qtbase/qt_cmdline.cmake

            if self.compiler.is_clang():
                self.throw(
                    "QT6 compilation not supported with clang up to v15.0.6 on windows: more investigations needed here."
                )
                cmake_args = '-DCMAKE_SUPPRESS_DEVELOPER_WARNINGS=1 -DCMAKE_CXX_FLAGS="-Wno-ignored-pragmas -Wno-deprecated-builtins"'

                cxx_path = self.compiler.get_cxx_path()
                logger.info("Was using cxx path: %s", cxx_path)
                folder = self.get_parent_folder(cxx_path)

                # use clang-cl instead for the compilation here:
                self.env["CC"] = self.get_path(folder, "clang-cl.exe")
                self.env["CXX"] = self.get_path(folder, "clang-cl.exe")

                # Skipping qtdoc as we have an issue with missing zlib or something like that:
                # Skipping qtlanguageserver because the build is crashing with our version of LLVM ?
                # args = "-optimize-size -platform win32-clang-msvc -optimize-full -c++std c++20"
                args = "-optimize-full -platform win32-clang-msvc -opensource -confirm-license"
                args += " -skip qtdoc -skip qtlanguageserver -skip qtconnectivity -skip qtspeech"
                args += " -skip qtquick3dphysics"

                # This below doesn't really work when buildting QT6Core:
                # zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
                # z_lib = "zlib.lib"
                # cmake_args += f" -DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}"
                # cmake_args += f" -DZLIB_INCLUDE_DIR={zlib_dir}/include"

                # Also having an hard time compiling the snappy library (dep from chromium) with clang-cl 15.0.4 :-(
                # Also not working with llvm 15.0.6
                # Testing with LLVM 14.0.6: also failing to build snappy (and D3D compiler ?) :-|
            else:
                # MSVC compiler:
                cmake_args = "-DCMAKE_SUPPRESS_DEVELOPER_WARNINGS=1"

                # Only optimize-size supported on MSVC (cf. qtbase/configure.cmake & qtbase/cmake/QtCompilerOptimization.cmake)
                # but we patched that below.
                # Note: if we use c++20, then we cannot compile qtconnectivity/qtspeech
                # args = "-optimize-size -optimize-full -platform win32-msvc -c++std c++20 -skip qtconnectivity -skip qtspeech"
                args = "-optimize-full -platform win32-msvc -opensource -confirm-license"

            self.generate_qt_config(build_dir, prefix, args, cmake_args)

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
            ndesc = {
                "nodejs_version": "18.13.0",
                "packages": [],
                "install_dir": build_dir,
            }

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
            tgt_file = f"{build_dir}/qtbase/qt_cmdline.cmake"
            self.patch_file(
                tgt_file,
                "qt_commandline_option(optimize-size TYPE boolean NAME optimize_size)",
                "qt_commandline_option(optimize-size TYPE boolean NAME optimize_size)\nqt_commandline_option(optimize-full TYPE boolean NAME optimize_full)",
            )

            # The patch below doesn't seem to be really needed:
            # tgt_file = f"{build_dir}/qtwebengine/cmake/Functions.cmake"
            # self.patch_file(tgt_file, "visual_studio_version=2019", "visual_studio_version=2022")

            if self.compiler.is_clang():
                tgt_file = f"{build_dir}/qtbase/configure.cmake"
                self.patch_file(
                    tgt_file,
                    "qt_find_package(WrapSystemZLIB",
                    "#qt_find_package(WrapSystemZLIB",
                )
                self.patch_file(
                    tgt_file,
                    "set_property(TARGET ZLIB::ZLIB PROPERTY IMPORTED_GLOBAL TRUE)",
                    "#set_property(TARGET ZLIB::ZLIB PROPERTY IMPORTED_GLOBAL TRUE)",
                )

                # cannot compile qdoc:
                tgt_file = f"{build_dir}/qttools/src/CMakeLists.txt"
                self.patch_file(tgt_file, "add_subdirectory(qdoc)", "#add_subdirectory(qdoc)")

                # nor lupdate:
                tgt_file = f"{build_dir}/qttools/src/linguist/CMakeLists.txt"
                self.patch_file(tgt_file, "add_subdirectory(lupdate)", "#add_subdirectory(lupdate)")

                # Disable usage of lld-link and using link.exe instead:
                tgt_file = f"{build_dir}/qtwebengine/src/gn/CMakeLists.txt"
                self.patch_file(
                    tgt_file,
                    "set(GN_LINKER ${CMAKE_LINKER})",
                    "set(GN_LINKER link.exe)",
                )

            cmd = [
                self.tools.get_cmake_path(),
                "-DOPTFILE=config.opt",
                "-DTOP_LEVEL=TRUE",
                "-P",
                f"{build_dir}/qtbase/cmake/QtProcessConfigureArgs.cmake",
                "-Wno-dev",
            ]

            self.check_execute(cmd, cwd=build_dir, env=self.env)

        # Building the library now:
        logger.info("Building QT6 libraries...")
        cmd = [self.tools.get_cmake_path(), "--build", ".", "--parallel"]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        # Testing direct execution of ninja to get mode debug outputs:
        # self.exec_ninja(build_dir, ["-v"])

        logger.info("Installing QT6 libraries...")
        cmd = [self.tools.get_cmake_path(), "--install", "."]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        pyenv.remove_py_env("qt6_env")

        # Remove the previous out build folder if needed:
        if self.dir_exists(prev_build_dir):
            logger.info("Removing previous QT build folder %s", prev_build_dir)
            self.remove_folder(prev_build_dir, recursive=True)

        # Restoring the build folder doesn't really work as we try to delete it after with too long file names:
        # self.rename_folder(build_dir, prev_build_dir)

        # So we must directly delete the folder out of source
        logger.info("Removing out of source build dir %s", build_dir)
        self.remove_folder(build_dir, recursive=True)

        logger.info("Done building QT6.")

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for QT6 on linux"""

        # Note: really need to install the following packages:
        # pkg-config
        # libnss3-dev libdbus-1-dev libcups2-dev libxkbcommon-dev libx11-xcb-dev
        # libx11-dev
        # libx11-xcb-dev
        # libxext-dev
        # libxfixes-dev
        # libxi-dev
        # libxrender-dev
        # libxcb1-dev
        # libxcb-glx0-dev
        # libxcb-keysyms1-dev
        # libxcb-image0-dev
        # libxcb-shm0-dev
        # libxcb-icccm4-dev
        # libxcb-sync-dev
        # libxcb-xfixes0-dev
        # libxcb-shape0-dev
        # libxcb-randr0-dev
        # libxcb-render-util0-dev
        # libxcb-util-dev
        # libxcb-xinerama0-dev
        # libxcb-xkb-dev
        # libxkbcommon-dev
        # libxkbcommon-x11-dev
        # Additional libs for WebEngine:
        # libx11-dev libdrm-dev libxcomposite-dev libxcursor-dev libxrandr-dev libxi-dev x11proto-core-dev libxshmfence-dev libxtst-dev libxkbfile-dev libsecret-1-dev
        # X11:YES LIBDRM:YES XCOMPOSITE:NO XCURSOR:NO XRANDR:NO XI:YES XPROTO:YES XSHMFENCE:NO XTST:NO
        # Also perl is already available on my system.
        # => cf. https://doc.qt.io/qt-6/linux-requirements.html

        # Use our static icu library:
        icu_dir = self.man.get_library_root_dir("icu")

        # Append the entries to the env:
        self.compiler.append_cxxflag(f"-I{icu_dir}/include")
        self.compiler.append_cflag(f"-I{icu_dir}/include")
        self.compiler.append_ldflag(f"-L{icu_dir}/lib")
        self.compiler.append_lib("-l:libicui18n.a")
        self.compiler.append_lib("-l:libicuuc.a")
        self.compiler.append_lib("-l:libicudata.a")

        # Trying to set the number of threads to use (but not sure this is really working ?)
        num_threads = max(min(self.cpu_count() - 4, 32), 1)
        self.env["CMAKE_BUILD_PARALLEL_LEVEL"] = f"{num_threads}"

        cmake_args = " ".join(
            [
                "-DCMAKE_SUPPRESS_DEVELOPER_WARNINGS=1",
                '-DCMAKE_CXX_FLAGS="-Wno-ignored-pragmas -Wno-deprecated-builtins"',
                f"-DICU_ROOT={icu_dir}",
            ]
        )

        args = [
            "-optimize-full",
            "-opensource",
            "-confirm-license",
            "-release",
            "-qt-doubleconversion",
            "-qt-pcre",
            "-qt-zlib",
            "-qt-freetype",
            "-qt-harfbuzz",
            "-qt-libpng",
            "-qt-libjpeg",
            "-qt-sqlite",
            "-qt-tiff",
            "-qt-webp",
            "-skip",
            "qtwebengine",
            "-skip",
            "qtquick3dphysics",
        ]

        if self.compiler.is_emcc():
            # get the host path for QT:
            host_path = prefix.replace("linux_emcc", "linux_clang")
            logger.info("QT host path is: %s", host_path)
            self.check(self.dir_exists(host_path), "QT host path must exists.")

            args += [
                f"-qt-host-path {host_path}",
                "-platform wasm-emscripten",
                "-no-warnings-are-errors",
                "-feature-thread",
                "-static",
                # "-skip",
                # "qtquick3d",
            ]
        else:
            args += [
                "-icu",
                "-openssl-runtime",
                "-xcb-xlib",
                "-xcb",
            ]

        # "-qt-assimp", "-webengine-icu=qt", "-qt-webengine-ffmpeg", "-qt-webengine-opus", "-qt-webengine-webp",
        args = " ".join(args)

        self.generate_qt_config(build_dir, prefix, args, cmake_args)

        # prepare the python env:
        pyenv = self.ctx.get_component("pyenvs")
        pdesc = {"inherit": "default_env", "packages": ["html5lib"]}

        pyenv.add_py_env_desc("qt6_env", pdesc)

        pyenv.setup_py_env("qt6_env")
        py_dir = pyenv.get_py_env_dir("qt6_env")
        # Need the bin folder here too:
        py_dir = self.get_path(py_dir, "qt6_env/bin")

        # Prepare a nodejs env:
        nodejs = self.ctx.get_component("nodejs")

        # On linux the node app is in the bin subfolder:
        nodejs_dir = self.get_path(build_dir, "qt6_env/bin")
        ndesc = {"nodejs_version": "18.13.0", "packages": [], "install_dir": build_dir}
        # Should work with nodejs 18, see fix for node path below:
        # ndesc = {"nodejs_version": "12.22.9", "packages": [], "install_dir": build_dir}

        nodejs.setup_nodejs_env("qt6_env", env_dir=build_dir, desc=ndesc, update_npm=True)

        gperf_dir = self.tools.get_tool_dir("gperf")
        bison_dir = self.tools.get_tool_dir("bison")
        flex_dir = self.tools.get_tool_dir("flex")

        # patch the node.py file to use our nodejs binary:
        tgt_file = f"{build_dir}/qtwebengine/src/3rdparty/chromium/third_party/node/node.py"
        self.patch_file(tgt_file, "nodejs = which('nodejs')", f"nodejs = '{nodejs_dir}/node'")

        # nss_root_dir = self.man.get_library_root_dir("nss").replace("\\", "/")
        # nss_dir = self.get_path(nss_root_dir, "Release/bin")
        # self.append_cflag(f"-I{nss_root_dir}/public/nss")
        # self.append_linkflag(f"-L{nss_root_dir}/Release/lib")

        dirs = [
            self.get_path(build_dir, "qtbase", "bin"),
            py_dir,
            nodejs_dir,
            gperf_dir,
            bison_dir,
            flex_dir,
            # nss_dir,
            # self.get_path(perl_dir, "perl", "site", "bin"),
            # self.get_path(perl_dir, "perl", "bin"),
            # self.get_path(perl_dir, "c", "bin"),
        ]
        logger.info("Adding additional paths: %s", dirs)

        # Need to prepend the folders in the linux case:
        self.env = self.prepend_env_list(dirs, self.env)

        logger.info("Environment paths: %s", self.env["PATH"])

        # Also add NODEJS_HOME in the env:
        self.env["NODEJS_HOME"] = nodejs_dir

        # Apply the required patches:
        tgt_file = f"{build_dir}/qtbase/qt_cmdline.cmake"
        self.patch_file(
            tgt_file,
            "qt_commandline_option(optimize-size TYPE boolean NAME optimize_size)",
            "qt_commandline_option(optimize-size TYPE boolean NAME optimize_size)\nqt_commandline_option(optimize-full TYPE boolean NAME optimize_full)",
        )

        # Configuration step:
        cmd = [
            self.tools.get_cmake_path(),
            "-DOPTFILE=config.opt",
            "-DTOP_LEVEL=TRUE",
            "-P",
            f"{build_dir}/qtbase/cmake/QtProcessConfigureArgs.cmake",
            "-Wno-dev",
        ]

        self.check_execute(cmd, cwd=build_dir, env=self.env)

        # Building the library now:
        logger.info("Building QT6 libraries...")
        cmd = [self.tools.get_cmake_path(), "--build", ".", "--parallel"]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        # Testing direct execution of ninja to get mode debug outputs:
        # self.exec_ninja(build_dir, ["-v"])

        logger.info("Installing QT6 libraries...")
        cmd = [self.tools.get_cmake_path(), "--install", "."]
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        pyenv.remove_py_env("qt6_env")
