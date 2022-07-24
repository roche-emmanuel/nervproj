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
        self.construct_frame = None
        self.handlers_path = None

    @property
    def settings(self):
        """retrieve the settings from the context."""
        return self.ctx.get_settings()

    @property
    def platform(self):
        """retrieve the platform from the context."""
        return self.ctx.get_platform()

    def set_construct_frame(self, frame):
        """Assign a construct frame to this component"""
        self.construct_frame = frame
        # setup the default handlers path:
        parts = self.construct_frame["module"].split(".")

        # Replace the last name on the module path with "handlers"
        parts[-1] = "handlers"
        self.handlers_path = ".".join(parts)

    def get_component(self, cname, do_init=True):
        """Retrieve a component from the context"""
        return self.ctx.get_component(cname, do_init)

    def create_component(self, cname, args=None, do_init=True):
        """Create a new instance of a component"""
        return self.ctx.create_component(cname, args=args, do_init=do_init)

    def get_param(self, pname, defval=None):
        """Retrieve a given parameter from the context
        or the default value."""

        val = self.ctx.get_settings().get(pname, None)
        if val is None:
            val = defval
        return val

    def get_config(self):
        """Get the config from this component"""
        return self.config

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
        process the full command path."""
        return self.process_cmd_path(self.ctx.get_command_path())

    def process_cmd_path(self, _cmd):
        """Process the full command path"""
        return False

    def run(self):
        """Run this component as main"""
        self.ctx.parse_args(False)
        cmd = self.ctx.get_command(0)
        res = self.process_command(cmd)
        if res is not True:
            args = self.ctx.get_additional_args()
            logger.warning("Cannot process command '%s' (additional args: %s)", cmd, args)

    def call_handler(self, hname, *args, **kwargs):
        """Call a given handler"""
        return self.ctx.call_handler(hname, *args, **kwargs)

    def handle(self, hname, *args, **kwargs):
        """Call an handler specific to this component, should be found
        in a sub folder called 'handlers'"""
        return self.call_handler(f"{self.handlers_path}.{hname}", self, *args, **kwargs)
