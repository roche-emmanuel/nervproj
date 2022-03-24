"""Collection of admin utility functions"""
import os
import sys
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = AdminManager(ctx)
    ctx.register_component('admin', comp)


class AdminManager(NVPComponent):
    """Admin command manager class"""

    def __init__(self, ctx: NVPContext):
        """Admin commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        # # Check the value of the sub command:
        # sub_cmd = self.settings['l1_cmd']
        # if sub_cmd == 'install-cli':
        #     self.install_cli()

        desc = {
            "admin": {
                "install": {"cli": None, "reqs": None, "repo": None},
            }
        }
        ctx.define_subparsers("main", desc)

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

        script_path = self.get_path(self.ctx.get_root_dir(), "cli.sh")

        # If we are on windows, we may want to convert this path to a cygwin path
        # if we are in a cygwin environment (but running the native python executable):
        if self.ctx.is_windows():
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

    def install_python_requirements(self):
        """Install the requirements for the main python environment using pip"""

        logger.info("Installing python requirements...")
        reqfile = self.get_path(self.ctx.get_root_dir(), "tools/requirements.txt")
        cmd = [sys.executable, "-m", "pip", "install", "-r", reqfile]
        # logger.info("Executing command: %s", cmd)
        self.execute(cmd)
        logger.info("Done installing python requirements.")

    def install_repository_bootstrap(self):
        """Install the bootstraped repository for this NervProj folder if not present already."""

        base_dir = self.ctx.get_root_dir()
        if self.dir_exists(base_dir, ".git"):
            logger.info(".git folder already exists, bootstrapping ignored.")
            return

        # We need to bootstrap in a temp folder:
        git = self.get_component('git')

        url = self.config["repository_url"]

        dest_dir = self.get_path(base_dir, "temp", "nervproj")
        logger.info("Cloning NervProj folder into %s...", dest_dir)
        git.clone_repository(url, dest_dir)

        # When cloning is done we should move the .git folder from the clone location into our root
        self.move_path(self.get_path(dest_dir, ".git"), self.get_path(base_dir, ".git"))

        # And finally we remove the remaining files:
        self.remove_folder(dest_dir)

        logger.info("Done bootstrapping NervProj project.")

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 != 'admin':
            return False

        cmd1 = self.ctx.get_command(1)
        cmd2 = self.ctx.get_command(2)
        if cmd1 == 'install' and cmd2 == 'cli':
            self.install_cli()
            return True

        if cmd1 == 'install' and cmd2 == 'reqs':
            self.install_python_requirements()
            return True

        if cmd1 == 'install' and cmd2 == 'repo':
            self.install_repository_bootstrap()
            return True

        return False
