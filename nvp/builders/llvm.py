"""This module provide the builder for the LLVM library."""
# cf. https://llvm.org/docs/CMake.html

import logging

from nvp.components.build import BuildManager
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
        self.common_flags = ["-DLLVM_TARGETS_TO_BUILD=X86",
                             "-DLLVM_ENABLE_EH=ON", "-DLLVM_ENABLE_RTTI=ON",
                             "-DLLVM_BUILD_TOOLS=ON", "-DLLVM_ENABLE_RUNTIMES=libc;libcxx;libcxxabi;libunwind;openmp",
                             "-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libclc;lld;lldb;polly;pstl",
                             "-DLLVM_STATIC_LINK_CXX_STDLIB=OFF", "-DLLVM_INCLUDE_TOOLS=ON",
                             "-DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=OFF"]

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
        iconv_lib = "libiconvStatic.lib" if self.is_windows else "libiconv.a"

        self.append_compileflag(f"-I{iconv_dir}/include")
        self.append_linkflag(f"-L{iconv_dir}/lib")
        self.append_linkflag(f"-l{iconv_lib}")

        # This is not needed/not working: using the patch below instead:
        # f"-DLIBC_INSTALL_LIBRARY_DIR={prefix}/lib",

        return self.common_flags + [f"-DLIBCXX_INSTALL_LIBRARY_DIR={prefix}/lib",
                                    f"-DLIBCXX_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
                                    f"-DLIBCXX_INSTALL_INCLUDE_TARGET_DIR={prefix}/include/c++/v1",
                                    f"-DLIBCXXABI_INSTALL_LIBRARY_DIR={prefix}/lib",
                                    f"-DLIBUNWIND_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
                                    f"-DLIBUNWIND_INSTALL_LIBRARY_DIR={prefix}/lib",
                                    f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
                                    f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
                                    f"-DLIBXML2_LIBRARY={xml2_dir}/lib/{xml2_lib}",
                                    f"-DLIBXML2_INCLUDE_DIR={xml2_dir}/include/libxml2",
                                    ]

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

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for LLVM on windows"""

        # Apply the patches:
        self.apply_patches(build_dir)

        # Create a sub build folder:
        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        flags = self.get_cmake_flags(prefix)
        self.run_cmake(build_dir, prefix, "../llvm", flags)
        self.run_ninja(build_dir)

        # other possible options:
        # -DLLVM_BUILD_TOOLS=ON -DLLVM_INCLUDE_TOOLS=ON
        # -DLLVM_BUILD_EXAMPLES=ON   -DLLVM_ENABLE_IDE=OFF  ..\llvm

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for LLVM on linux"""

        # Apply the patches:
        self.apply_patches(build_dir)

        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        flags = self.get_cmake_flags(prefix)
        self.run_cmake(build_dir, prefix, "../llvm", flags)
        self.run_ninja(build_dir)
