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

    @property
    def settings(self):
        """retrieve the settings from the context."""
        return self.ctx.get_settings()
