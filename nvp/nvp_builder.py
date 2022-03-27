"""NVP project class"""
import logging
from nvp.components.build import BuildManager

from nvp.nvp_object import NVPObject

logger = logging.getLogger(__name__)


class NVPBuilder(NVPObject):
    """Simple Builder class"""

    def __init__(self, bman: BuildManager):
        """Initialize this builder"""
        self.ctx = bman.ctx
        self.man = bman
        self.compiler = bman.compiler
        self.env = None
        self.tools = self.ctx.get_component('tools')

    def build(self, build_dir, prefix, desc):
        """Run the build process either on the proper target platform"""
        self.env = self.compiler.get_env()
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
