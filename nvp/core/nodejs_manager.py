"""NodeJs manager component"""
import logging
import os

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return NodeJsManager(ctx)


class NodeJsManager(NVPComponent):
    """NodeJsManager component"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

    def get_env_desc(self, env_name):
        """Retrieve the desc for a given environment"""
        # If there is a current project we first search in that one:
        proj = self.ctx.get_current_project()
        desc = None
        if proj is not None:
            desc = proj.get_nodejs_env(env_name)

        if desc is None:
            # Then search in all projects:
            projs = self.ctx.get_projects()
            for proj in projs:
                desc = proj.get_nodejs_env(env_name)
                if desc is not None:
                    break

        if desc is None:
            all_envs = self.config.get("nodejs_envs", {})
            desc = all_envs.get(env_name, None)

        assert desc is not None, f"Cannot find nodejs environment with name {env_name}"
        return desc

    def get_env_dir(self, env_name, desc=None):
        """Retrieve the installation dir for a given nodejs env."""
        if desc is None:
            desc = self.get_env_desc(env_name)

        default_env_dir = self.get_path(self.ctx.get_root_dir(), ".nodeenvs")
        return desc.get("install_dir", default_env_dir)

    def remove_nodejs_env(self, env_name, env_dir=None):
        """Remove a nodejs env given by name"""
        desc = self.get_env_desc(env_name)

        if env_dir is None:
            # try to use the install dir from the desc if any or use the default install dir:
            env_dir = self.get_env_dir(env_name, desc)

        # create the env folder if it doesn't exist yet:
        dest_folder = self.get_path(env_dir, env_name)

        if self.dir_exists(dest_folder):
            logger.info("Removing nodejs environment at %s", dest_folder)
            self.remove_folder(dest_folder)

    def get_root_dir(self, env_name):
        """Retrieve the root directory for a given environment"""
        env_dir = self.get_env_dir(env_name)
        return self.get_path(env_dir, env_name)

    def get_node_path(self, env_name, desc=None):
        """Retrieve the full path to node in a given environment."""
        env_dir = self.get_env_dir(env_name, desc)
        ext = ".exe" if self.is_windows else ""
        prefix = "" if self.is_windows else "bin/"
        node_path = self.get_path(env_dir, env_name, f"{prefix}node{ext}")
        self.check(self.file_exists(node_path), "Invalid node path: %s", node_path)
        return node_path

    def run_node(self, env_name, args):
        """Execute a node command"""
        node_path = self.get_node_path(env_name)
        cmd = [node_path] + args
        self.execute(cmd)

    def run_npm(self, env_name, args, desc=None):
        """Execute a npm command"""
        if desc is None:
            desc = self.get_env_desc(env_name)
        env_dir = self.get_env_dir(env_name, desc)
        root_path = self.get_path(env_dir, env_name)

        node_path = self.get_node_path(env_name, desc)

        prefix = "" if self.is_windows else "lib/"
        npm_script = self.get_path(root_path, f"{prefix}node_modules", "npm", "bin", "npm-cli.js")
        cmd = [node_path, npm_script] + args

        # We should add node to the env path:
        env = os.environ.copy()

        node_dir = self.get_parent_folder(node_path)
        env = self.prepend_env_list(node_dir, env)

        self.execute(cmd, env=env)

    def setup_nodejs_env(self, env_name, env_dir=None, renew_env=False, update_npm=False, desc=None):
        """Setup a given nodejs environment"""

        if desc is None:
            desc = self.get_env_desc(env_name)

        if env_dir is None:
            # try to use the install dir from the desc if any or use the default install dir:
            env_dir = self.get_env_dir(env_name, desc)

        # Ensure the parent folder exists:
        self.make_folder(env_dir)

        # create the env folder if it doesn't exist yet:
        dest_folder = self.get_path(env_dir, env_name)

        tools = self.get_component("tools")
        new_env = False

        if self.dir_exists(dest_folder) and renew_env:
            logger.info("Removing previous python environment at %s", dest_folder)
            self.remove_folder(dest_folder)

        if not self.dir_exists(dest_folder):
            # Should extract the nodejs package first:
            vers = desc["nodejs_version"]
            ext = ".7z" if self.is_windows else ".tar.xz"
            suffix = "win-x64" if self.is_windows else "linux-x64"
            base_name = f"node-v{vers}-{suffix}"
            filename = f"{base_name}{ext}"

            pkg_dir = self.get_path(self.ctx.get_root_dir(), "tools", self.platform)
            pkg_file = self.get_path(pkg_dir, filename)
            if not self.file_exists(pkg_file):
                logger.info("Downloading nodejs version %s for %s...", vers, self.platform)
                url = f"https://nodejs.org/dist/v{vers}/{filename}"
                tools.download_file(url, pkg_file)

            logger.info("Installing nodejs version %s...", vers)
            tools.extract_package(pkg_file, env_dir, target_dir=dest_folder, extracted_dir=base_name)
            new_env = True

        if new_env or update_npm:
            # Update the npm installation:
            # self.run_npm(env_name, args=["update", "--location=global", "npm"], desc=desc)
            self.run_npm(env_name, args=["update", "-g", "npm"], desc=desc)

        # self.run_node(env_name, args=["--version"])

        # trigger the update of pip:
        packages = desc["packages"]
        if len(packages) > 0:
            logger.info("Installing packages: %s", packages)
            self.run_npm(env_name, args=["install", "--location=global"] + packages, desc=desc)

        # self.run_npm(env_name, args=["update", "--location=global"])

    def process_cmd_path(self, cmd):
        """Process a given command path"""

        if cmd == "setup":
            env_name = self.get_param("env_name")
            env_dir = self.get_param("env_dir")
            renew_env = self.get_param("renew_env", False)
            update_npm = self.get_param("update_npm", False)
            # logger.info("Should setup environment %s here.", env_name)
            self.setup_nodejs_env(env_name, env_dir, renew_env, update_npm)
            return True

        if cmd == "remove":
            env_name = self.get_param("env_name")
            env_dir = self.get_param("env_dir")
            # logger.info("Should remove environment %s here.", env_name)
            self.remove_nodejs_env(env_name, env_dir)
            return True

        return False


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("nodejs", NodeJsManager(context))

    psr = context.build_parser("setup")
    psr.add_str("env_name")("Name of the environment to setup")
    psr.add_str("--dir", dest="env_dir")("Environments root dir")
    psr.add_flag("--update-npm", dest="update_npm")("Request the update of npm")
    psr.add_flag("--renew", dest="renew_env")("Renew the environment completely")

    psr = context.build_parser("remove")
    psr.add_str("env_name")("Name of the environment to remove")
    psr.add_str("--dir", dest="env_dir")("Environments root dir")

    comp.run()
