"""Collection of admin utility functions"""
# import re
import configparser
import logging
import os

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_object import NVPCheckError

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return GitManager(ctx)


class GitManager(NVPComponent):
    """Git command manager class"""

    def __init__(self, ctx: NVPContext):
        """Git commands manager constructor"""
        NVPComponent.__init__(self, ctx)

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

        logger.info("Validating git setup in home dir '%s'", home_dir)
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
        ssh_keys = ssh_cfg.get("keys", {})

        # add support to call ssh app here:
        ssh = "ssh"
        if self.is_windows:
            tools = self.get_component("tools")
            git_dir = tools.get_tool_root_dir("git")
            ssh = self.get_path(git_dir, "usr", "bin", "ssh.exe")

        # prepare an environment with the desired home:
        env = os.environ.copy()
        env["HOME"] = home_dir

        ports = ssh_cfg.get("ports", {})

        for kfile, urls in ssh_keys.items():
            key_file = self.get_path(ssh_dir, kfile)
            if not self.file_exists(key_file):
                logger.info("Installing ssh private key %s", key_file)
                src = self.ctx.select_first_valid_path(urls)
                assert src is not None, f"No valid path provided for {key_file}"
                self.copy_file(src, key_file)
                self.set_chmod(key_file, "600")

                # Get the server name from the key:
                if kfile.startswith("id_rsa_") and kfile.endswith("_git"):
                    sname = kfile[7:-4]
                    # sname = re.sub('^id_rsa_', '', kfile)
                    # sname = re.sub('_git$', '', sname)
                    logger.info("Adding %s to known_hosts...", sname)
                    port = ports.get(sname, 22)
                    cmd = [ssh, "-q", "-o", "StrictHostKeyChecking=no", f"git@{sname}", "-p", str(port)]
                    logger.debug("Executing command %s", cmd)
                    self.execute(cmd, env=env, check=False)

        cfg_file = self.get_path(home_dir, ".gitconfig")

        if not self.file_exists(cfg_file):
            logger.info("Creating global gitconfig file %s", cfg_file)
            config = configparser.ConfigParser()
            config["user"] = {
                "email": user_email,
                "name": user_name,
            }

            self.write_ini(config, cfg_file)
        else:
            # Otherwise we read the content from that file and we check the current user email/name:
            config = self.read_ini(cfg_file)
            save_needed = False

            if "user" not in config:
                logger.info("Adding user section in git config.")
                config["user"] = {
                    "email": user_email,
                    "name": user_name,
                }
                save_needed = True
            else:
                user = config["user"]
                if user["email"] != user_email:
                    logger.info("Updating git user email from %s to %s", user["email"], user_email)
                    user["email"] = user_email
                    save_needed = True

                if user["name"] != user_name:
                    logger.info("Updating git user name from %s to %s", user["name"], user_name)
                    user["name"] = user_name
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

    def process_cmd_path(self, cmd):
        """Process a given command path"""

        if cmd == "clone":
            pname = self.get_param("project")
            proj = self.ctx.get_project(pname)
            dest_dir = self.get_param("dest_folder")
            self.clone_project_repository(dest_dir, proj)
            return True

        if cmd == "commit":
            msg = self.get_param("message")
            cwd = self.get_canonical_cwd()
            self.commit_all(msg, cwd)
            return True

        if cmd == "status":
            cwd = self.get_canonical_cwd()
            self.git_status(cwd)
            return True

        if cmd == "diff":
            cwd = self.get_canonical_cwd()
            self.git_diff(cwd)
            return True

        if cmd == "push":
            cwd = self.get_canonical_cwd()
            self.git_push(cwd)
            return True

        if cmd == "pull":
            cwd = self.get_canonical_cwd()
            self.git_pull(cwd)
            return True

        if cmd == "setup":
            # Setup the git configuration
            self.setup_global_config()
            return True

        if cmd == "pullall":
            # Pull all the known repositories:
            # We start with the NVP framework itself:
            logger.info("Pulling NVP framework...")
            self.git_pull(self.ctx.get_root_dir())

            # Next we iterate on all the projects:
            for proj in self.ctx.get_projects():
                ppath = proj.get_root_dir()
                # Check if this is a valid git repo:
                if ppath is not None and self.path_exists(ppath, ".git") and proj.auto_git_sync():
                    logger.info("Pulling %s...", proj.get_name())
                    try:
                        self.git_pull(ppath)
                    except NVPCheckError:
                        logger.error("Could not pull repository %s", proj.get_name())
            return True

        if cmd == "pushall":
            # Push all the known repositories:
            # We start with the NVP framework itself:
            logger.info("Pushing NVP framework...")
            self.git_push(self.ctx.get_root_dir())

            # Next we iterate on all the projects:
            for proj in self.ctx.get_projects():
                ppath = proj.get_root_dir()
                if ppath is not None and self.path_exists(ppath, ".git") and proj.auto_git_sync():
                    logger.info("Pushing %s...", proj.get_name())
                    try:
                        self.git_push(ppath)
                    except NVPCheckError:
                        logger.error("Could not push repository %s", proj.get_name())
            return True

        return False

    def execute_git(self, args, cwd=None):
        """execute a git command with the provided arguments"""
        tools = self.get_component("tools")
        cmd = [tools.get_git_path()] + args

        # Execute the command:
        logger.debug("git command: %s", cmd)
        res, rcode, outs = self.execute(cmd, cwd=cwd)

        if not res:
            logger.error("git command %s (in %s) failed with return code %d:\n%s", cmd, cwd, rcode, outs)
            self.throw("Detected git command failure.")

    def clone_repository(self, url, dest_folder, mirror=False, recurse=False):
        """Clone a given url into a given folder"""

        # Ensure the parent folder exists:
        base_dir = self.get_parent_folder(dest_folder)
        self.make_folder(base_dir)

        cmd = ["clone", "--progress"]
        if mirror:
            cmd.append("--mirror")
        if recurse:
            cmd.append("--recurse-submodules")

        cmd += [url, dest_folder]
        self.execute_git(cmd)

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

        # Here we should also setup the git user as needed:
        user_name = proj.get_config().get("git_user_name", None)
        user_email = proj.get_config().get("git_user_email", None)

        if user_name is None and user_email is None:
            return

        logger.info("Adding user section in git config.")
        cfg_file = self.get_path(dest_folder, ".git", "config")
        assert self.file_exists(cfg_file), f"Cannot fine git config file at {cfg_file}"
        # Load that config:
        config = self.read_ini(cfg_file)
        config["user"] = {
            "email": user_email,
            "name": user_name,
        }

        self.write_ini(config, cfg_file)

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

    def git_checkout(self, folder, discard=False, branch=None):
        """perform git pull from a given folder"""
        cmd = ["checkout"]
        if discard:
            cmd += ["--", "."]
        if branch is not None:
            cmd += [branch]

        self.execute_git(cmd, cwd=folder)

    def git_fetch(self, folder, url=None):
        """perform git fetch in a given folder"""
        cmd = ["fetch"]
        if url is not None:
            cmd.append(url)
        self.execute_git(cmd, cwd=folder)

    def git_gc(self, folder, url=None):
        """perform git gc in a given folder"""
        cmd = ["gc"]
        if url is not None:
            cmd.append(url)
        self.execute_git(cmd, cwd=folder)

    def git_prune(self, folder, url=None):
        """perform git prune in a given folder"""
        cmd = ["prune"]
        if url is not None:
            cmd.append(url)
        self.execute_git(cmd, cwd=folder)

    def commit_all(self, msg, folder, do_push=True):
        """Commit all changes from a given folder"""

        self.execute_git(["add", "-A", "."], cwd=folder)
        self.execute_git(["commit", "-a", "-m", msg], cwd=folder)

        if do_push:
            self.git_push(folder)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("git")

    context.define_subparsers("main", ["status", "diff", "setup", "push", "pull", "pullall", "pushall"])

    psr = context.build_parser("clone")
    psr.add_str("dest_folder", nargs="?", default=None)(help="Name of the folder where to checkout the project")
    psr.add_str("-p", "--project", dest="project")(help="The project that should be cloned.")

    psr = context.build_parser("commit")
    psr.add_str("message")(help="Commit message")

    comp.run()
