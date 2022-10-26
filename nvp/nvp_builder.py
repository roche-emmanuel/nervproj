"""NVP builder class"""

import logging

from nvp.core.build_manager import BuildManager
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
        self.tools = self.ctx.get_component("tools")
        desc = desc or {}
        self.tool_envs = desc.get("tool_envs", ["ninja"])

    def init_env(self):
        """Init the compiler environment"""
        self.env = self.compiler.get_env()

        # Add the tools to the path:
        tdirs = [self.tools.get_tool_dir(tname) for tname in self.tool_envs]
        self.env = self.prepend_env_list(tdirs, self.env)

        if self.is_linux:
            # We should add the -fPIC flag to the CXXFLAGS:
            flags = self.env.get("CXXFLAGS", "")
            self.env["CXXFLAGS"] = f"{flags} -fPIC"
            flags = self.env.get("CFLAGS", "")
            self.env["CFLAGS"] = f"{flags} -fPIC"

    def build(self, build_dir, prefix, desc):
        """Run the build process either on the proper target platform"""
        self.init_env()

        if self.is_windows:
            self.build_on_windows(build_dir, prefix, desc)
        elif self.is_linux:
            self.build_on_linux(build_dir, prefix, desc)
        else:
            raise NotImplementedError

    def append_cxxflag(self, val):
        """Append a value to the cxxflags environment var"""
        flags = self.env.get("CXXFLAGS", "")
        self.env["CXXFLAGS"] = f"{flags} {val}"

    def append_cflag(self, val):
        """Append a value to the cflags environment var"""
        flags = self.env.get("CFLAGS", "")
        self.env["CFLAGS"] = f"{flags} {val}"

    def append_ldflag(self, val):
        """Append a value to the ldflags environment var"""
        flags = self.env.get("LDFLAGS", "")
        self.env["LDFLAGS"] = f"{flags} {val}"

    def append_compileflag(self, val):
        """Append a value to both the cxxflags and cflags"""
        self.append_cxxflag(val)
        self.append_cflag(val)

    def append_linkflag(self, val):
        """Append a value to both the ldflags"""
        self.append_ldflag(val)

    def build_on_windows(self, build_dir, prefix, desc):
        """Run the build operation. Should be re-implemented."""
        raise NotImplementedError

    def build_on_linux(self, build_dir, prefix, desc):
        """Run the build operation. Should be re-implemented."""
        raise NotImplementedError

    def check_execute(self, cmd, *args, **kwargs):
        """Run a command and throw if we get an error."""
        res, rcode, _ = self.execute(cmd, *args, **kwargs)
        if res is False:
            self.throw(
                "Error when executing build operation:\nCommand '%s' finished with return code %d.\n=> Stopping build process.",
                cmd,
                rcode,
            )

    def exec_ninja(self, build_dir, flags=None, **kwargs):
        """Run a custom ninja command line"""
        ninja_path = self.tools.get_ninja_path()
        flags = flags or []
        self.check_execute([ninja_path] + flags, cwd=build_dir, env=self.env, **kwargs)

    def run_ninja(self, build_dir, flags=None, **kwargs):
        """Execute the standard ninja build/install commands"""
        self.exec_ninja(build_dir, flags=flags, **kwargs)
        self.exec_ninja(build_dir, ["install"], **kwargs)

    def run_make(self, build_dir, **kwargs):
        """Execute the standard make build/install commands"""
        self.check_execute(["make"], cwd=build_dir, env=self.env, **kwargs)
        self.check_execute(["make", "install"], cwd=build_dir, env=self.env, **kwargs)

    def run_cmake(self, build_dir, prefix, src_dir=None, flags=None, generator="Ninja", **kwargs):
        """Execute Standard cmake configuration command"""
        build_type = kwargs.get("build_type", "Release")
        cmd = [
            self.tools.get_cmake_path(),
            "-G",
            generator,
            f"-DCMAKE_BUILD_TYPE={build_type}",
            f"-DCMAKE_INSTALL_PREFIX={prefix}",
        ]
        if flags is not None:
            cmd += flags

        # Add the source directory:
        if src_dir is not None:
            cmd.append(src_dir)

        logger.info("Cmake command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env, **kwargs)

    def run_configure(self, build_dir, prefix, flags=None, src_dir=None):
        """Execute Standard configure command"""
        if src_dir is None:
            src_dir = build_dir

        cmd = ["sh", self.get_path(src_dir, "configure"), f"--prefix={prefix}"]
        if flags is not None:
            cmd += flags

        logger.info("configure command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)
