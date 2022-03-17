"""Collection of admin utility functions"""
import os
import logging
import re
import pprint

import distutils

from modules.manager_base import ManagerBase

logger = logging.getLogger(__name__)


class AdminManager(ManagerBase):
    """Admin command manager class"""

    def __init__(self, settings):
        """Admin commands manager constructor"""
        ManagerBase.__init__(self, settings)

        # Check the value of the sub command:
        sub_cmd = settings['sub_cmd']
        if sub_cmd == 'install-cli':
            self.install_cli()

    def install_cli(self):
        """Install a CLI script in .bashrc if application"""

        # Check if an $HOME folder is provider:
        home_dir = os.getenv('HOME')
        if home_dir is None:
            logger.error("Cannot install cli alias: no $HOME environment variable detected.")
            return

        logger.info("Home folder is: %s", home_dir)

        # Check if we have a .bashrc file in that folder:
        bashrc_file = self.get_path(home_dir, ".bashrc")
        if not self.file_exists(bashrc_file):
            logger.warning("Cannot install cli alias: no .bashrc file in HOME folder.")
            return

        script_path = self.get_path(self.root_dir, "cli.sh")

        # If we are on windows, we may want to convert this path to a cygwin path
        # if we are in a cygwin environment (but running the native python executable):
        if self.is_windows():
            script_path = self.to_cygwin_path(script_path)
            assert script_path is not None, "Invalid cygwin environment."

        sline = f"\n[ -f \"{script_path}\" ] && source \"{script_path}\"\n"

        # Check if this string is already in the bashrc file:
        content = self.read_text_file(bashrc_file)

        if content.find(sline) == -1:
            # We should add the string:
            logger.info("Adding source file in .bashrc for NervProj")

            # Make a backup of the file:
            self.copy_file(bashrc_file, bashrc_file+".bak", force=True)
            self.write_text_file(content+sline, bashrc_file, newline='\n')
        else:
            logger.info("NervProj setup file already referenced in .bashrc")

        # pp = pprint.PrettyPrinter(indent=2)
        # res = pp.pformat(dict(os.environ))
        # logger.info("Current environment is: %s", res)
