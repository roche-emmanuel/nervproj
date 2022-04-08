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
                "push": None,
                "pull": None,
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

    def validate_git_global_config(self, home_dir):
        """Validate the git/ssh global setup in the given "home" folder"""
        user_email = self.config["git"]["user_email"]
        user_name = self.config["git"]["user_name"]

        # Here we also need to ensure we have the required ssh key/config installed in our .ssh folder:
        ssh_dir = self.get_path(home_dir, ".ssh")
        self.make_folder(ssh_dir)
        self.set_chmod(ssh_dir, "700")

        ssh_cfg = self.config["ssh"]

        # Install the ssh config:
        cfg_file = self.get_path(ssh_dir, "config")
        if not self.file_exists(cfg_file):
            logger.info("Installing ssh config in %s", ssh_dir)
            urls = ssh_cfg["config_urls"]
            src = self.ctx.select_first_valid_path(urls)
            assert src is not None, "No valid path provided as ssh config source"
            self.copy_file(src, cfg_file)
            self.set_chmod(ssh_dir, "600")

        # Install the SSH keys:
        ssh_keys = ssh_cfg.get('keys', {})

        # keep known hosts values:
        # known_hosts = []
        # tools = self.get_component("tools")
        # git_dir = tools.get_git_path()
        # keyscan

        for kfile, urls in ssh_keys.items():
            key_file = self.get_path(ssh_dir, kfile)
            if not self.file_exists(key_file):
                logger.info("Installing ssh private key %s", key_file)
                src = self.ctx.select_first_valid_path(urls)
                assert src is not None, f"No valid path provided for {key_file}"
                self.copy_file(src, key_file)
                self.set_chmod(ssh_dir, "600")

                # Get the server name from the key:
                # sname = kfile.replace("id_rsa_", "").replace("_git")
                # logger.info("Adding %s to known_hosts...")
                # # cmd = ["ssh.exe", "-o", "StrictHostKeyChecking=no",  sname,  "ls"]
                # keyscan = self.get_path()
                # cmd = ["ssh-keyscan.exe", "-o", "StrictHostKeyChecking=no",  sname,  "ls"]

        cfg_file = self.get_path(home_dir, ".gitconfig")

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

            if 'user' not in config:
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
        self.validate_git_global_config(self.ctx.get_home_dir())

        # if on windows we should also setup the gitconfig in our "windows home"
        # even if $HOME is currently pointing to cygwin home:
        if self.ctx.is_cygwin():
            # Get/use the canonical windows home:
            self.validate_git_global_config(self.get_win_home_dir())

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
            self.git_status(cwd)
            return True

        if cmd1 == 'diff':
            cwd = self.get_canonical_cwd()
            self.git_diff(cwd)
            return True

        if cmd1 == 'push':
            cwd = self.get_canonical_cwd()
            self.git_push(cwd)
            return True

        if cmd1 == 'pull':
            cwd = self.get_canonical_cwd()
            self.git_pull(cwd)
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

    def git_status(self, folder):
        """Retrieve the git status from a given folder"""
        self.execute_git(["status"], cwd=folder)

    def git_diff(self, folder):
        """Retrieve the git diff from a given folder"""
        self.execute_git(["diff"], cwd=folder)

    def git_push(self, folder):
        """perform git push from a given folder"""
        self.execute_git(["push"], cwd=folder)

    def git_pull(self, folder):
        """perform git pull from a given folder"""
        self.execute_git(["pull"], cwd=folder)
