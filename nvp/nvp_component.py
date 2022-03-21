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
        self.settings = ctx.get_settings()
        self.config = ctx.get_config()
