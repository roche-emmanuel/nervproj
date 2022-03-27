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
        self.tool_envs = desc.get('tool_envs', ['ninja'])

    def build(self, build_dir, prefix, desc):
        """Run the build process either on the proper target platform"""
        self.env = self.compiler.get_env()

        # Add the tools to the path:
        tdirs = [self.tools.get_tool_dir(tname) for tname in self.tool_envs]
        self.env = self.prepend_env_path(tdirs, self.env)

        if self.is_windows:
            return self.build_on_windows(build_dir, prefix, desc)
        if self.is_linux:
            return self.build_on_linux(build_dir, prefix, desc)

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
