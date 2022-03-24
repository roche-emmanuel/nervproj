"""Collection of admin utility functions"""
import logging
import configparser

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = GitManager(ctx)
    ctx.register_component('git', comp)


class GitManager(NVPComponent):
    """Git command manager class"""

    def __init__(self, ctx: NVPContext):
        """Git commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        desc = {
            "git": {
                "clone": None,
                "status": None,
                "diff": None,
                "setup": None,
            }
        }
        ctx.define_subparsers("main", desc)
        psr = ctx.get_parser('main.git.clone')
        psr.add_argument("dest_folder", type=str, nargs='?', default=None,
                         help="Name of the folder where to checkout the project")

    def get_canonical_cwd(self):
        """Retrieve canonical root folder to use depending on if we have a current
        project or not."""

        # Check if we have a proj assigned, and if not, we use the current CWD :
        proj = self.ctx.get_current_project()
        if proj is not None:
            cwd = proj.get_root_dir()
            assert cwd is not None, f"No local path available for project {proj.get_name()}"
            return cwd

        return self.get_cwd()

    def validate_git_global_config(self, cfg_file):
        """Validate the git global config file settings
        mainly checking the user email and name for now."""
        user_email = self.config["git"]["user_email"]
        user_name = self.config["git"]["user_name"]

        if not self.file_exists(cfg_file):
            logger.info("Creating global gitconfig file %s", cfg_file)
            config = configparser.ConfigParser()
            config['user'] = {
                "email": user_email,
                "name": user_name,
            }

            self.write_ini(config, cfg_file)
        else:
            # Otherwise we read the content from that file and we check the current user email/name:
            config = self.read_ini(cfg_file)
            save_needed = False

            if not 'user' in config:
                logger.info("Adding user section in git config.")
                config['user'] = {
                    "email": user_email,
                    "name": user_name,
                }
                save_needed = True
            else:
                user = config['user']
                if user['email'] != user_email:
                    logger.info("Updating git user email from %s to %s", user['email'], user_email)
                    user['email'] = user_email
                    save_needed = True

                if user['name'] != user_name:
                    logger.info("Updating git user name from %s to %s", user['name'], user_name)
                    user['name'] = user_name
                    save_needed = True

            if save_needed:
                self.write_ini(config, cfg_file)

    def setup_global_config(self):
        """Setup the git configration overall"""
        cfg_file = self.get_path(self.ctx.get_home_dir(), ".gitconfig")
        self.validate_git_global_config(cfg_file)

        # if on windows we should also setup the gitconfig in our "windows home"
        # even if $HOME is currently pointing to cygwin home:
        if self.ctx.is_cygwin():
            # Get the canonical windows home:
            home_dir = self.get_win_home_dir()
            cfg_file = self.get_path(home_dir, ".gitconfig")
            self.validate_git_global_config(cfg_file)

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 != 'git':
            return False

        cmd1 = self.ctx.get_command(1)
        # cmd2 = self.ctx.get_command(2)
        if cmd1 == 'clone':
            self.clone_project_repository(self.settings['dest_folder'])
            return True

        if cmd1 == 'status':
            cwd = self.get_canonical_cwd()
            self.get_status(cwd)
            return True

        if cmd1 == 'diff':
            cwd = self.get_canonical_cwd()
            self.get_diff(cwd)
            return True

        if cmd1 == 'setup':
            # Setup the git configuration
            self.setup_global_config()
            return True

        return False

    def execute_git(self, args, cwd=None):
        """execute a git command with the provided arguments"""
        tools = self.get_component('tools')
        cmd = [tools.get_git_path()]+args

        # Execute the command:
        logger.debug("git command: %s", cmd)
        self.execute(cmd, cwd=cwd)

    def clone_repository(self, url, dest_folder):
        """Clone a given url into a given folder"""

        # Ensure the parent folder exists:
        base_dir = self.get_parent_folder(dest_folder)
        self.make_folder(base_dir)

        self.execute_git(["clone", url, dest_folder])

    def clone_project_repository(self, dest_folder=None, proj=None):
        """Checkout the repository for the given project into the given local folder"""
        if proj is None:
            proj = self.ctx.get_current_project()

        if dest_folder is None:
            dest_folder = proj.get_name(False)

        # check if dest_folder is relative or absolute:
        if self.is_relative_path(dest_folder):
            logger.info("Current CWD: %s", self.get_cwd())
            dest_folder = self.get_path(self.get_cwd(), dest_folder)

        # get the project url:
        url = proj.get_repository_url()

        self.clone_repository(url, dest_folder)

    def get_status(self, folder):
        """Retrieve the git status from a given folder"""
        self.execute_git(["status"], cwd=folder)

    def get_diff(self, folder):
        """Retrieve the git diff from a given folder"""
        self.execute_git(["diff"], cwd=folder)
