"""Collection of admin utility functions"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return PyEnvManager(ctx)


class PyEnvManager(NVPComponent):
    """PyEnvManager component used to run scripts commands on the sub projects"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

        self.scripts = ctx.get_config().get("scripts", {})

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "setup":
            env_name = self.get_param("env_name")
            self.setup_py_env(env_name)
            return True

        if cmd == "remove":
            env_name = self.get_param("env_name")
            self.remove_py_env(env_name)
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

    def add_py_env_desc(self, env_name, desc):
        """Add a python environment desc to the list manually"""
        envs = self.config.get("custom_python_envs")
        self.check(env_name not in envs, "Python environment desc %s already exists.", env_name)
        envs[env_name] = desc

    def get_py_env_dir(self, env_name, desc=None):
        """Retrieve the installation dir for a given py env."""
        if desc is None:
            desc = self.get_py_env_desc(env_name)

        default_env_dir = self.get_path(self.ctx.get_root_dir(), ".pyenvs")
        return desc.get("install_dir", default_env_dir)

    def remove_py_env(self, env_name):
        """Remove a pyenv given by name"""
        desc = self.get_py_env_desc(env_name)
        env_dir = self.get_param("env_dir")

        if env_dir is None:
            # try to use the install dir from the desc if any or use the default install dir:
            env_dir = self.get_py_env_dir(env_name, desc)

        # create the env folder if it doesn't exist yet:
        dest_folder = self.get_path(env_dir, env_name)

        if self.dir_exists(dest_folder):
            logger.info("Removing python environment at %s", dest_folder)
            self.remove_folder(dest_folder)

    def get_all_packages(self, desc):
        """Retrieve all the python packages requested for a given environment desc"""
        pkgs = []

        if "inherit" in desc:
            parent_name = desc["inherit"]
            pdesc = self.get_py_env_desc(parent_name)
            pkgs = self.get_all_packages(pdesc)

        # Add the packages from this desc:
        added = desc["packages"]
        for pkg in added:
            if pkg not in pkgs:
                pkgs.append(pkg)

        # Return all the packages:
        return pkgs

    def get_all_modules(self, desc):
        """Retrieve the list of modules that should be installed in the python environment"""
        mods = {}

        if "inherit" in desc:
            parent_name = desc["inherit"]
            pdesc = self.get_py_env_desc(parent_name)
            mods = self.get_all_modules(pdesc)

        # Add the packages from this desc:
        added = desc.get("additional_modules", {})
        for mname, mpath in added.items():
            if mname in mods and mpath != mods[mname]:
                logger.info("Overriding additional module %s: %s => %s", mname, mods[mname], mpath)

            mods[mname] = mpath

        # Return all the modules:
        return mods

    def setup_py_env(self, env_name):
        """Setup a given python environment"""

        desc = self.get_py_env_desc(env_name)
        env_dir = self.get_param("env_dir")

        if env_dir is None:
            # try to use the install dir from the desc if any or use the default install dir:
            env_dir = self.get_py_env_dir(env_name, desc)

        # Ensure the parent folder exists:
        self.make_folder(env_dir)

        # create the env folder if it doesn't exist yet:
        dest_folder = self.get_path(env_dir, env_name)

        tools = self.get_component("tools")
        new_env = False

        if self.dir_exists(dest_folder) and self.get_param("renew_env"):
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

        py_path = self.get_path(dest_folder, pdesc["sub_path"])

        if new_env or self.get_param("update_pip"):
            # trigger the update of pip:
            logger.info("Updating pip...")
            self.execute([py_path, "-m", "pip", "install", "--upgrade", "pip", "--no-warn-script-location"])

        # Next we should prepare the requirements file:
        req_file = self.get_path(dest_folder, "requirements.txt")

        # First we install the "wheel" package:
        content = "wheel"
        self.write_text_file(content, req_file)
        logger.info("Installing base packages...")
        self.execute([py_path, "-m", "pip", "install", "-r", req_file, "--no-warn-script-location"])

        packages = self.get_all_packages(desc)

        content = "\n".join(packages)
        self.write_text_file(content, req_file)

        logger.info("Installing python requirements...")
        self.execute([py_path, "-m", "pip", "install", "-r", req_file, "--no-warn-script-location"])

        # Also install the additional modules if any:
        mods = self.get_all_modules(desc)

        tools = self.get_component("tools")

        for mname, mpath in mods.items():
            logger.info("Installing module %s...", mname)
            dest_path = self.get_path(dest_folder, mname)
            tools.download_file(mpath, dest_path)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    # comp = context.register_component("pyenvs", PyEnvManager(context))
    comp = context.get_component("pyenvs")

    psr = context.build_parser("setup")
    psr.add_str("env_name")("Name of the environment to setup")
    psr.add_str("--dir", dest="env_dir")("Environments root dir")
    psr.add_flag("--update-npm", dest="update_npm")("Request the update of npm")
    psr.add_flag("--renew", dest="renew_env")("Renew the environment completely")

    psr = context.build_parser("remove")
    psr.add_str("env_name")("Name of the environment to remove")
    psr.add_str("--dir", dest="env_dir")("Environments root dir")

    comp.run()