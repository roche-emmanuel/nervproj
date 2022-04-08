"""NVP builder class"""

import logging
from nvp.components.build import BuildManager

from nvp.nvp_object import NVPObject

logger = logging.getLogger(__name__)


class NVPBuilder(NVPObject):
    """Simple Builder class"""

    def __init__(self, bman: BuildManager, desc=None):
        """Initialize this builder"""
        self.ctx = bman.ctx
        self.man = bman
        self.compiler = bman.compiler
        self.env = None
        self.tools = self.ctx.get_component('tools')
        desc = desc or {}
        self.tool_envs = desc.get('tool_envs', ['ninja'])

    def build(self, build_dir, prefix, desc):
        """Run the build process either on the proper target platform"""
        self.env = self.compiler.get_env()

        # Add the tools to the path:
        tdirs = [self.tools.get_tool_dir(tname) for tname in self.tool_envs]
        self.env = self.prepend_env_list(tdirs, self.env)

        if self.is_windows:
            self.build_on_windows(build_dir, prefix, desc)
        elif self.is_linux:
            # We should add the -fPIC flag to the CXXFLAGS:
            if "CXXFLAGS" in self.env:
                self.env["CXXFLAGS"] = self.env["CXXFLAGS"] +" -fPIC"
            else:
                self.env["CXXFLAGS"] = "-fPIC"
            self.build_on_linux(build_dir, prefix, desc)
        else:
            raise NotImplementedError

    def build_on_windows(self, build_dir, prefix, desc):
        """Run the build operation. Should be re-implemented."""
        raise NotImplementedError

    def build_on_linux(self, build_dir, prefix, desc):
        """Run the build operation. Should be re-implemented."""
        raise NotImplementedError

    def run_ninja(self, build_dir):
        """Execute the standard ninja build/install commands"""
        ninja_path = self.tools.get_ninja_path()
        self.execute([ninja_path], cwd=build_dir, env=self.env)
        self.execute([ninja_path, "install"], cwd=build_dir, env=self.env)

    def run_make(self, build_dir):
        """Execute the standard make build/install commands"""
        self.execute(["make"], cwd=build_dir, env=self.env)
        self.execute(["make", "install"], cwd=build_dir, env=self.env)

    def run_cmake(self, build_dir, prefix, src_dir, flags=None, generator="Ninja"):
        """Execute Standard cmake configuration command"""
        cmd = [self.tools.get_cmake_path(), "-G", generator, "-DCMAKE_BUILD_TYPE=Release",
               f"-DCMAKE_INSTALL_PREFIX={prefix}"]
        if flags is not None:
            cmd += flags

        # Add the source directory:
        cmd.append(src_dir)

        logger.info("Cmake command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=self.env)

    def run_configure(self, build_dir, prefix, flags=None, src_dir=None):
        """Execute Standard configure command"""
        if src_dir is None:
            src_dir = build_dir

        cmd = ["sh", self.get_path(src_dir, "configure"), f"--prefix={prefix}"]
        if flags is not None:
            cmd += flags

        logger.info("configure command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=self.env)
