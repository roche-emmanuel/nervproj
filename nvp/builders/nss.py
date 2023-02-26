"""This module provide the builder for the nss library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("nss", Builder(bman))


class Builder(NVPBuilder):
    """nss builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        raise NotImplementedError()

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        # cf. https://firefox-source-docs.mozilla.org/security/nss/build.html#mozilla-projects-nss-building

        # We will need a python environment with gyp-next here:
        # prepare the python env:
        pyenv = self.ctx.get_component("pyenvs")
        pdesc = {"inherit": "default_env", "packages": ["gyp-next"]}

        pyenv.add_py_env_desc("nss_env", pdesc)

        pyenv.setup_py_env("nss_env")
        py_dir = pyenv.get_py_env_dir("nss_env")
        # Need the bin folder here too:
        py_dir = self.get_path(py_dir, "nss_env/bin")

        # And we also need ninja in the path:
        ninja_dir = self.tools.get_tool_dir("ninja")

        dirs = [
            py_dir,
            ninja_dir,
        ]
        logger.info("Adding additional paths: %s", dirs)

        # Need to prepend the folders in the linux case:
        self.env = self.prepend_env_list(dirs, self.env, key="PATH")

        # We also need the include/lib dirs from nspr:
        nspr_dir = self.man.get_library_root_dir("nspr").replace("\\", "/")
        inc_dir = self.get_path(nspr_dir, "include/nspr")
        lib_dir = self.get_path(nspr_dir, "lib")

        script = self.get_path(build_dir, "build.sh")
        cmd = [script, "-v", "-j", "4", "-c", "-o", "--clang", "-t",
               "x64", f"--with-nspr={inc_dir}:{lib_dir}", "--static", "--disable-tests"]
        logger.info("build command: %s", cmd)

        self.check_execute(cmd, cwd=build_dir, env=self.env)

        # Move the sibling "dist" folder as install path:
        parent_dir = self.get_parent_folder(build_dir)
        dist_dir = self.get_path(parent_dir, "dist")

        self.rename_folder(dist_dir, prefix)
