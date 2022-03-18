"""Collection of gitlab utility functions"""
import logging

from nvp.manager_base import ManagerBase

logger = logging.getLogger(__name__)


class GitlabManager(ManagerBase):
    """Gitlab command manager class"""

    def __init__(self, settings):
        """Gitlab commands manager constructor"""
        ManagerBase.__init__(self, settings)

        # Check the value of the sub command:
        cmd0 = settings['l0_cmd']
        cmd1 = settings['l1_cmd']

        logger.info("Running gitlab manager with command %s %s", cmd0, cmd1)
