"""Collection of filesystem utility functions"""
import logging
from nvp.nvp_context import NVPContext
from nvp.nvp_object import NVPObject


logger = logging.getLogger(__name__)


class NVPComponent(NVPObject):
    """Base component class"""

    def __init__(self, ctx: NVPContext):
        """Manager base constructor"""
        self.ctx = ctx
        self.config = ctx.get_config()
        self.initialized = False

    @property
    def settings(self):
        """retrieve the settings from the context."""
        return self.ctx.get_settings()

    @property
    def flavor(self):
        """retrieve the flavor from the context."""
        return self.ctx.get_flavor()

    @property
    def platform(self):
        """retrieve the platform from the context."""
        return self.ctx.get_platform()

    def get_component(self, cname, do_init=True):
        """Retrieve a component from the context"""
        return self.ctx.get_component(cname, do_init)

    def is_initialized(self):
        """Return initialization state."""
        return self.initialized

    def initialize(self):
        """Initialize this component."""
        self.initialized = True

    def process_command(self, _cmd0):
        """Default implementation of process_command,
        returns False here by default."""
        return False
