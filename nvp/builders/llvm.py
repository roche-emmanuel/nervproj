"""This module provide the builder for the LLVM library."""
# cf. https://llvm.org/docs/CMake.html

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('LLVM', LLVMBuilder(bman, {
        'tool_envs': ['ninja', 'python']
    }))


class LLVMBuilder(NVPBuilder):
    """LLVM builder class."""

    def __init__(self, bman: BuildManager, desc):
        NVPBuilder.__init__(self, bman, desc)

        # "-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libc;libclc;lld;lldb;openmp;polly;pstl",
        # "-DBUILD_SHARED_LIBS=OFF",
        # "-DLLVM_ENABLE_RUNTIMES=all"
        #
        # "-DLLVM_ENABLE_RUNTIMES='libcxx;libcxxabi'"
        # "-DLLVM_ENABLE_RUNTIMES=libc;libcxx;libcxxabi;libunwind;openmp",

        self.common_flags = ["-DLLVM_TARGETS_TO_BUILD=X86",
                             "-DLLVM_ENABLE_EH=ON", "-DLLVM_ENABLE_RTTI=ON",
                             "-DLLVM_BUILD_TOOLS=ON",
                             "-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libclc;lld;lldb;polly;pstl",
                             "-DLLVM_STATIC_LINK_CXX_STDLIB=OFF", "-DLLVM_INCLUDE_TOOLS=ON",
                             "-DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=OFF",
                             "-DLLVM_ENABLE_LIBXML2=ON"]

    def get_cmake_flags(self, prefix):
        """Retrive the applicable cmake flags for the build"""

        # Also add the zlib/libxml2 paths here:
        # note libxml2 seems to be required to get llvm-mt to work on windows (?)
        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        xml2_dir = self.man.get_library_root_dir("libxml2").replace("\\", "/")

        z_lib = "zlibstatic.lib" if self.is_windows else "libz.a"
        xml2_lib = "libxml2s.lib" if self.is_windows else "libxml2.a"

        # Note: we also need to add libiconv to the include/link flags:
        iconv_dir = self.man.get_library_root_dir("libiconv").replace("\\", "/")
        iconv_lib = "libiconvStatic.lib" if self.is_windows else "iconv"

        self.append_compileflag(f"-DLIBXML_STATIC -I{iconv_dir}/include -I{xml2_dir}/include/libxml2")
        if self.is_windows:
            self.append_linkflag(f"/LIBPATH:{xml2_dir}/lib {xml2_lib}")
            self.append_linkflag(f"/LIBPATH:{iconv_dir}/lib {iconv_lib}")
            self.append_linkflag("Ws2_32.lib")
        else:
            self.append_linkflag("-Wl,-Bstatic")
            self.append_linkflag(f"-L{iconv_dir}/lib")
            self.append_linkflag(f"-L{xml2_dir}/lib")
            self.append_linkflag("-lxml2")
            self.append_linkflag(f"-l{iconv_lib}")
            self.append_linkflag("-Wl,-Bdynamic")
            # self.append_linkflag(f"{iconv_lib}")

        # This is not needed/not working: using the patch below instead:
        # f"-DLIBC_INSTALL_LIBRARY_DIR={prefix}/lib",

        flags = self.common_flags + [
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DLIBXML2_LIBRARY={xml2_dir}/lib/{xml2_lib}",
            f"-DLIBXML2_INCLUDE_DIR={xml2_dir}/include/libxml2",
        ]

        if self.is_linux:
            flags += [f"-DLIBCXX_INSTALL_LIBRARY_DIR={prefix}/lib",
                      f"-DLIBCXX_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
                      f"-DLIBCXX_INSTALL_INCLUDE_TARGET_DIR={prefix}/include/c++/v1",
                      f"-DLIBCXXABI_INSTALL_LIBRARY_DIR={prefix}/lib",
                      f"-DLIBUNWIND_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
                      f"-DLIBUNWIND_INSTALL_LIBRARY_DIR={prefix}/lib",
                      "-DLLVM_ENABLE_RUNTIMES=libc;libcxx;libcxxabi;libunwind;openmp"
                      ]

        return flags

    def apply_patches(self, build_dir):
        """Apply the required patches for the build"""

        # Fix the libc installation folder:
        libc_file = self.get_path(build_dir, "libc", "lib", "CMakeLists.txt")
        self.replace_in_file(libc_file,
                             "set(LIBC_INSTALL_LIBRARY_DIR lib${LLVM_LIBDIR_SUFFIX}/${LLVM_DEFAULT_TARGET_TRIPLE})",
                             "set(LIBC_INSTALL_LIBRARY_DIR lib)")
        self.replace_in_file(libc_file,
                             "set(LIBC_INSTALL_LIBRARY_DIR lib${LLVM_LIBDIR_SUFFIX})",
                             "set(LIBC_INSTALL_LIBRARY_DIR lib)")

        # Force using libxml2 in config.h
        # cfg_file = self.get_path(build_dir, "llvm", "cmake", "modules", "LLVMConfig.cmake.in")
        # self.replace_in_file(cfg_file,
        #                      "set(LLVM_ENABLE_LIBXML2 @LLVM_ENABLE_LIBXML2@)",
        #                      "set(LLVM_ENABLE_LIBXML2 ON)")
        # cfg_file = self.get_path(build_dir, "llvm", "include", "llvm", "Config", "config.h.cmake")
        # self.replace_in_file(cfg_file,
        #                      "#cmakedefine LLVM_ENABLE_LIBXML2 ${LLVM_ENABLE_LIBXML2}",
        #                      "#cmakedefine LLVM_ENABLE_LIBXML2 1")

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for LLVM on windows"""

        # Apply the patches:
        self.apply_patches(build_dir)

        # Create a sub build folder:
        build_dir1 = self.get_path(build_dir, "build")
        self.make_folder(build_dir1)

        flags = self.get_cmake_flags(prefix)
        self.run_cmake(build_dir1, prefix, "../llvm", flags)

        # After configuration we need to fix the config.h file:
        cfg_file = self.get_path(build_dir, "build", "include", "llvm", "Config", "config.h")
        self.replace_in_file(cfg_file,
                             "/* #undef LLVM_ENABLE_LIBXML2 */",
                             "#define LLVM_ENABLE_LIBXML2 1")

        self.run_ninja(build_dir1)

        # other possible options:
        # -DLLVM_BUILD_TOOLS=ON -DLLVM_INCLUDE_TOOLS=ON
        # -DLLVM_BUILD_EXAMPLES=ON   -DLLVM_ENABLE_IDE=OFF  ..\llvm

        # On windows, When done building the compiler we should then build the runtimes:
        # cf. https://libcxx.llvm.org/BuildingLibcxx.html#cmake-visual-studio

        # Should also add git bash shell to the path:
        # and we should explicitly add the path to clang-cl to PATH:
        base_dir = self.tools.get_tool_root_dir('git')
        logger.info("Using git base path: %s", base_dir)
        pdirs = self.env.get("PATH", "")
        shell_dir = self.get_path(base_dir, "usr", "bin")
        clang_dir = self.get_path(prefix, "bin")
        self.env['PATH'] = f"{clang_dir};{shell_dir};{pdirs}"
        # Reset the previous env flags:
        if "CFLAGS" in self.env:
            del self.env["CFLAGS"]
        if "CXXFLAGS" in self.env:
            del self.env["CXXFLAGS"]
        if "LDFLAGS" in self.env:
            del self.env["LDFLAGS"]

        # next we create a build dir for the runtimes
        build_dir2 = self.get_path(build_dir, "build2")

        # **Important note**: Failure when building libc below
        # And also failure with openmp
        # And same for libunwind
        # And libcxxabi
        # "-DLLVM_ENABLE_RUNTIMES=libc;libcxx;libcxxabi;libunwind;openmp",
        # => Basically, we can only build libcxx here.

        # prepare the flags for cmake:
        flags = ["-S", "runtimes", "-B", "build2",
                 f"-DLIBCXX_INSTALL_LIBRARY_DIR={prefix}/lib",
                 f"-DLIBCXX_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
                 f"-DLIBCXX_INSTALL_INCLUDE_TARGET_DIR={prefix}/include/c++/v1",
                 "-DLIBCXX_ENABLE_EXPERIMENTAL_LIBRARY=NO",
                 #  f"-DLIBCXXABI_INSTALL_LIBRARY_DIR={prefix}/lib",
                 #  f"-DLIBUNWIND_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
                 #  f"-DLIBUNWIND_INSTALL_LIBRARY_DIR={prefix}/lib",
                 "-DLLVM_ENABLE_RUNTIMES=libcxx",
                 "-DCMAKE_C_COMPILER=clang-cl.exe",
                 "-DCMAKE_CXX_COMPILER=clang-cl.exe",
                 #  "-DLIBCXX_ENABLE_STATIC=OFF",
                 #  "-DLIBCXXABI_ENABLE_STATIC=OFF",
                 #  "-DLIBCXX_LINK_TESTS_WITH_SHARED_LIBCXXABI=ON",
                 #  "-DLIBUNWIND_ENABLE_STATIC=OFF",
                 ]

        logger.info("Building LLVM runtimes...")

        self.run_cmake(build_dir, prefix, flags=flags)

        # We also have to create the destination include/c++/v1 folder ourself here:
        # self.make_folder(build_dir2, "include", "c++", "v1")

        self.exec_ninja(build_dir2, ['cxx'])  # , 'cxxabi' , 'unwind'
        # Test are failing for now below:
        # self.exec_ninja(build_dir2, ['check-cxx'])  # , 'check-cxxabi' , 'check-unwind'
        self.exec_ninja(build_dir2, ['install-cxx'])  # , 'install-cxxabi' , 'install-unwind'

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for LLVM on linux"""

        # Apply the patches:
        self.apply_patches(build_dir)

        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        flags = self.get_cmake_flags(prefix)
        self.run_cmake(build_dir, prefix, "../llvm", flags)
        self.run_ninja(build_dir)
