"""NodeJs manager component"""
import logging

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

    def setup_nodejs_env(self, env_name, env_dir=None, renew_env=False, do_update=False):
        """Setup a given nodejs environment"""

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
            vers = desc['nodejs_version']
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

        # py_path = self.get_path(dest_folder, pdesc['sub_path'])

        # if new_env or do_update:
        #     # trigger the update of pip:
        #     logger.info("Updating pip...")
        #     self.execute([py_path, "-m", "pip", "install", "--upgrade", "pip"])

        # # Next we should prepare the requirements file:
        # req_file = self.get_path(dest_folder, "requirements.txt")
        # content = "\n".join(desc["packages"])
        # self.write_text_file(content, req_file)

        # logger.info("Installing python requirements...")
        # self.execute([py_path, "-m", "pip", "install", "-r", req_file])

    def process_cmd_path(self, cmd):
        """Process a given command path"""

        if cmd == "setup":
            env_name = self.get_param("env_name")
            logger.info("Should setup environment %s here.", env_name)
            env_dir = self.get_param("env_dir")
            renew_env = self.get_param("renew_env", False)
            do_update = self.get_param("do_update", False)
            self.setup_nodejs_env(env_name, env_dir, renew_env, do_update)
            return True

        if cmd == "remove":
            env_name = self.get_param("env_name")
            logger.info("Should remove environment %s here.", env_name)
            return True

        return False


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("nodejs", NodeJsManager(context))

    context.define_subparsers("main", ["setup", "remove"])

    psr = context.get_parser('main.setup')
    psr.add_argument("env_name", type=str,
                     help="Name of the environment to setup")
    psr = context.get_parser('main.remove')
    psr.add_argument("env_name", type=str,
                     help="Name of the environment to remove")

    comp.run()
