"""Collection of admin utility functions"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = PyEnvManager(ctx)
    ctx.register_component('pyenvs', comp)


class PyEnvManager(NVPComponent):
    """PyEnvManager component used to run scripts commands on the sub projects"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

        self.scripts = ctx.get_config().get("scripts", {})

        # Also extend the parser:
        ctx.define_subparsers("main", {'setup-pyenv': None})
        psr = ctx.get_parser('main.setup-pyenv')
        psr.add_argument("env_name", type=str,
                         help="Name of the python environment to setup/deploy")
        psr.add_argument("--dir", dest='env_dir', type=str,
                         help="Location where to install the environment")
        psr.add_argument("--renew", dest='renew_env', action='store_true',
                         help="Rebuild the environment completely")
        psr.add_argument("--update-pip", dest='update_pip', action='store_true',
                         help="Update pip module")

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == 'setup-pyenv':

            env_name = self.get_param('env_name')
            self.setup_py_env(env_name)
            return True

        return False

    def get_py_env_desc(self, env_name):
        """Retrieve the desc for a given python environment"""
        # If there is a current project we first search in that one:
        proj = self.ctx.get_current_project()
        desc = None
        if proj is not None:
            desc = proj.get_custom_python_env(env_name)

        if desc is None:
            # Then search in all projects:
            projs = self.ctx.get_projects()
            for proj in projs:
                desc = proj.get_custom_python_env(env_name)
                if desc is not None:
                    break

        if desc is None:
            all_envs = self.config.get("custom_python_envs")
            desc = all_envs.get(env_name, None)

        assert desc is not None, f"Cannot find python environment with name {env_name}"
        return desc

    def get_py_env_dir(self, env_name, desc=None):
        """Retrieve the installation dir for a given py env."""
        if desc is None:
            desc = self.get_py_env_desc(env_name)

        default_env_dir = self.get_path(self.ctx.get_root_dir(), ".pyenvs")
        return desc.get("install_dir", default_env_dir)

    def setup_py_env(self, env_name):
        """Setup a given python environment"""

        desc = self.get_py_env_desc(env_name)
        env_dir = self.get_param("env_dir")

        if env_dir is None:
            # try to use the install dir from the desc if any or use the default install dir:
            env_dir = self.get_py_env_dir(env_name, desc)

        # create the env folder if it doesn't exist yet:
        dest_folder = self.get_path(env_dir, env_name)

        tools = self.get_component("tools")
        new_env = False

        if self.dir_exists(dest_folder) and self.get_param('renew_env'):
            logger.info("Removing previous python environment at %s", dest_folder)
            self.remove_folder(dest_folder)

        pdesc = tools.get_tool_desc("python")

        if not self.dir_exists(dest_folder):
            # Should extract the python package first:
            logger.info("Extracting python package to %s", dest_folder)
            ext = "7z" if self.is_windows else "tar.xz"
            filename = f"python-{pdesc['version']}-{self.platform}.{ext}"
            pkg_file = self.get_path(self.ctx.get_root_dir(), "tools", "packages", filename)

            tools.extract_package(pkg_file, env_dir, target_dir=dest_folder, extracted_dir=f"python-{pdesc['version']}")
            new_env = True

        py_path = self.get_path(dest_folder, pdesc['sub_path'])

        if new_env or self.get_param("update_pip"):
            # trigger the update of pip:
            logger.info("Updating pip...")
            self.execute([py_path, "-m", "pip", "install", "--upgrade", "pip"])

        # Next we should prepare the requirements file:
        req_file = self.get_path(dest_folder, "requirements.txt")
        content = "\n".join(desc["packages"])
        self.write_text_file(content, req_file)

        logger.info("Installing python requirements...")
        self.execute([py_path, "-m", "pip", "install", "-r", req_file])
