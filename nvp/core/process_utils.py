"""ProcessUtils utility component"""
import logging
import os
import psutil

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return ProcessUtils(ctx)


class ProcessUtils(NVPComponent):
    """ProcessUtils component used to send automatic messages ono ProcessUtils server"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

    def get_cpu_usage_15mins(self):
        """Retrieve the CPU usage percent over the last 15 mins"""
        _, _, load15 = psutil.getloadavg()

        cpu_usage = (load15/os.cpu_count()) * 100.0
        return cpu_usage

    def get_ram_usage(self):
        """Retrieve RAM usage percent"""
        return psutil.virtual_memory()[2]
