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
    def platform(self):
        """retrieve the platform from the context."""
        return self.ctx.get_platform()

    def get_component(self, cname, do_init=True):
        """Retrieve a component from the context"""
        return self.ctx.get_component(cname, do_init)

    def get_param(self, pname, defval=None):
        """Retrieve a given parameter from the context
        or the default value."""

        val = self.ctx.get_settings().get(pname, None)
        if val is None:
            val = defval
        return val

    def load_config(self, cfgname, base_dir=None):
        """Load a configuration file from a given subpath"""
        if base_dir is None:
            base_dir = self.ctx.get_base_dir()
        cfg_file = self.get_path(base_dir, cfgname)

        # Load the configuration from that file:
        cfg = self.read_json(cfg_file)
        return cfg

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

    def run(self):
        """Run this component as main"""
        self.ctx.parse_args()
        cmd = self.ctx.get_command(0)
        res = self.process_command(cmd)
        if res is not True:
            logger.warning("Cannot process command '%s'", cmd)
