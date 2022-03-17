"""Collection of admin utility functions"""
import os
import logging

from manager_base import ManagerBase

logger = logging.getLogger(__name__)


class AdminManager(ManagerBase):
    """Admin command manager class"""

    def install_cli_alias(self, alias_name):
        """Install a CLI alias with the given name."""

        # Check if an $HOME folder is provider:
        home_dir = os.getenv('HOME')
        if home_dir is None:
            logger.error("Cannot install cli alias: no $HOME environment variable detected.")
            return

        logger.info("Home folder is: %s", home_dir)

        # Check if we have a .bashrc file in that folder:
        if not self.file_exists(self.get_path(home_dir, ".bashrc")):
            logger.warning("Cannot install cli alias: no .bashrc file in HOME folder.")
            return

        logger.info("Should check content of .bashrc file here.")
