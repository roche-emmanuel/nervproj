"""This module provide the builder for the LLVM library."""

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

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for LLVM on windows"""

        # Create a sub build folder:
        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        cmd = [self.tools.get_cmake_path(), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
               f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DLLVM_TARGETS_TO_BUILD=X86",
               "-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libc;libclc;lld;lldb;openmp;polly;pstl",
               "-DLLVM_ENABLE_EH=ON", "-DLLVM_ENABLE_RTTI=ON", "..\\llvm"]

        logger.info("Executing LLVM build command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=self.env)

        self.run_ninja(build_dir)

        # other possible options:
        # -DLLVM_BUILD_TOOLS=ON -DLLVM_INCLUDE_TOOLS=ON
        # -DLLVM_BUILD_EXAMPLES=ON   -DLLVM_ENABLE_IDE=OFF  ..\llvm

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for LLVM on linux"""

        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        cmd = [self.tools.get_cmake_path(), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
               f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DLLVM_TARGETS_TO_BUILD=X86",
               "-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libc;libclc;lld;lldb;openmp;polly;pstl",
               "-DLLVM_ENABLE_EH=ON", "-DLLVM_ENABLE_RTTI=ON",
               "../llvm"]

        logger.info("Executing LLVM build command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=self.env)

        self.run_ninja(build_dir)
