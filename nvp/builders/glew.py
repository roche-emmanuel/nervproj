"""This module provide the builder for the glew library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("glew", Builder(bman))


class Builder(NVPBuilder):
    """glew builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        flags = ["-DSSE=ON", "-DSTATIC=ON"]
        # if self.compiler.is_emcc():
        #     flags = ["-DBUILD_SHARED_LIBS=OFF"]

        # # Add NASM dir:
        # nasm_dir = self.tools.get_tool_dir("nasm")
        # self.prepend_env_list([nasm_dir], self.env)

        # self.run_cmake(build_dir, prefix, ".", flags=flags)
        # self.run_ninja(build_dir)

        self.throw("Building GLEW on windows not supported.")

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        # flags = ["-DSSE=ON", "-DSTATIC=ON"]
        # flags = ["-DBUILD_SHARED_LIBS=OFF"]
        # if self.compiler.is_emcc():
        #     flags = ["-DBUILD_SHARED_LIBS=OFF"]

        # self.run_make(build_dir)

        # We need to add python to the path:
        python_dir = self.tools.get_tool_dir("python")
        self.env = self.prepend_env_list([python_dir], self.env)

        # cf. https://github.com/nigels-com/glew/issues/31
        self.exec_make(build_dir, ["extensions", "PYTHON=python3", "SYSTEM=linux-clang", f"GLEW_DEST={prefix}"])
        self.exec_make(build_dir, ["all", "PYTHON=python3", "SYSTEM=linux-clang", f"GLEW_DEST={prefix}"])
        self.exec_make(build_dir, ["install", "PYTHON=python3", "SYSTEM=linux-clang", f"GLEW_DEST={prefix}"])
