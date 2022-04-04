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

        # return self.common_flags + [f"-DLIBCXX_INSTALL_LIBRARY_DIR={prefix}/lib", 
        #                             f"-DLIBCXX_INSTALL_INCLUDE_DIR={prefix}/include/c++/v1",
        #                             f"-DLIBCXX_INSTALL_INCLUDE_TARGET_DIR={prefix}/include/c++/v1"]
        return self.common_flags

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for LLVM on windows"""

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

        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        flags = self.get_cmake_flags(prefix)
        self.run_cmake(build_dir, prefix, "../llvm", flags)
        self.run_ninja(build_dir)
