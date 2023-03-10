"""This module provide the builder for the openssl library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("openssl", Builder(bman))


class Builder(NVPBuilder):
    """openssl builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        # cf. https://developers.refinitiv.com/en/article-catalog/article/how-to-build-openssl--zlib--and-curl-libraries-on-windows
        # Also see the INSTALL.md file for details
        self.check(self.compiler.is_msvc(), "Should build OpenSSL with MSVC compiler.")

        # Get the perl path:
        perl_dir = self.tools.get_tool_root_dir("perl")
        perl = self.tools.get_tool_path("perl")
        nasm_dir = self.tools.get_tool_root_dir("nasm")

        dirs = [
            nasm_dir,
            self.get_path(perl_dir, "perl", "site", "bin"),
            self.get_path(perl_dir, "perl", "bin"),
            self.get_path(perl_dir, "c", "bin"),
        ]
        logger.info("Adding additional paths: %s", dirs)

        self.env = self.append_env_list(dirs, self.env)

        cmd = [perl, "Configure", "VC-WIN64A", f"--prefix={prefix}", f"--openssldir={prefix}/ssl"]

        logger.info("Executing command: %s", cmd)

        self.check_execute(cmd, cwd=build_dir, env=self.env)

        # logger.info("ENV setup: %s", self.env)
        self.exec_nmake(build_dir)
        self.exec_nmake(build_dir, ["install"])
        self.exec_nmake(build_dir, ["test"])

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        cmd = ["./Configure", f"--prefix={prefix}", f"--openssldir={prefix}/ssl"]

        logger.info("Executing command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)

        self.run_make(build_dir)
