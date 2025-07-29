"""Collection of admin utility functions"""

import logging
import os

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

        if cmd == "update":
            env_name = self.get_param("env_name")
            pkg_name = self.get_param("pkg_name")
            self.update_package(env_name, pkg_name)
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

    def get_all_packages(self, desc, key):
        """Retrieve all the python packages requested for a given environment desc"""
        pkgs = []

        if "inherit" in desc:
            parent_name = desc["inherit"]
            pdesc = self.get_py_env_desc(parent_name)
            pkgs = self.get_all_packages(pdesc, key)

        # Add the packages from this desc:
        # Check first if we have platform specific packages:
        key_name = f"{self.platform}_{key}"
        added = desc[key_name] if key_name in desc else desc.get(key, [])
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

    def run_pip(self, py_path, args, env=None):
        """Run pip with the given args."""
        cmd = [py_path, "-m", "pip"]

        opts = ["--no-warn-script-location"]
        # Check if we have a valid cache dir:
        cache_dir = self.ctx.get_config().get("pip_cache_dir", None)
        if cache_dir is not None:
            cache_dir = self.ctx.select_first_valid_path(cache_dir)
            self.info("Using PIP cache dir: %s", cache_dir)
            opts += ["--cache-dir", cache_dir]

        self.execute(cmd + args + opts, env=env)

    def update_package(self, env_name, pkg_name):
        """Update a given python package in a given environment"""
        desc = self.get_py_env_desc(env_name)
        env_dir = self.get_param("env_dir")

        if env_dir is None:
            # try to use the install dir from the desc if any or use the default install dir:
            env_dir = self.get_py_env_dir(env_name, desc)

        dest_folder = self.get_path(env_dir, env_name)

        tools = self.get_component("tools")
        pdesc = tools.get_tool_desc("python")

        py_path = self.get_path(dest_folder, pdesc["sub_path"])

        logger.info("Updating %s...", pkg_name)
        self.run_pip(py_path, ["install", "--upgrade", pkg_name])

    def install_python_packages(self, py_path, packages, req_file, upgrade):
        """Install python packages in a given environment"""

        content = "\n".join(packages)
        self.write_text_file(content, req_file)

        # Should add git to the path here:
        tools = self.get_component("tools")
        git_path = tools.get_tool_path("git")
        git_dir = self.get_parent_folder(git_path)
        env = os.environ.copy()
        env = self.prepend_env_list([git_dir], env, "PATH")

        cmd = ["install"]
        if upgrade:
            cmd.append("--upgrade")
        cmd += ["-r", req_file]

        self.run_pip(py_path, cmd, env=env)

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
            # Check if a custom version should be used:
            pvers = pdesc["version"]
            if "version" in desc:
                pvers = desc["version"]

            # Should extract the python package first:
            logger.info("Extracting python package to %s", dest_folder)
            ext = "7z" if self.is_windows else "tar.xz"
            filename = f"python-{pvers}-{self.platform}.{ext}"
            pkg_file = self.get_path(self.ctx.get_root_dir(), "tools", "packages", filename)

            if not self.file_exists(pkg_file):
                pkg_urls = self.config.get("package_urls", [])
                pkg_urls = [base_url + "tools/" + filename for base_url in pkg_urls]

                pkg_url = self.ctx.select_first_valid_path(pkg_urls)
                self.check(pkg_url is not None, "Cannot find python package for %s", filename)
                tools.download_file(pkg_url, pkg_file)

            self.check(self.file_exists(pkg_file), "Could not retrieve python package %s", filename)

            tools.extract_package(pkg_file, env_dir, target_dir=dest_folder, extracted_dir=f"python-{pvers}")
            new_env = True

        py_path = self.get_path(dest_folder, pdesc["sub_path"])

        if new_env or self.get_param("update_pip"):
            # trigger the update of pip:
            logger.info("Updating pip...")
            self.run_pip(py_path, ["install", "--upgrade", "pip"])

        # Next we should prepare the requirements file:
        req_file = self.get_path(dest_folder, "requirements.txt")

        # First we install the "wheel" package:
        content = "wheel"
        self.write_text_file(content, req_file)
        logger.info("Installing base packages...")
        self.run_pip(py_path, ["install", "-r", req_file])

        # ensure the base packages are installed first:

        packages = self.get_all_packages(desc, "pre_packages")
        if len(packages) > 0:
            logger.info("Installing python pre_packages...")
            self.install_python_packages(py_path, packages, req_file, True)

        packages = self.get_all_packages(desc, "packages")
        if len(packages) > 0:
            logger.info("Installing python packages...")
            self.install_python_packages(py_path, packages, req_file, False)

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

    psr = context.build_parser("update")
    psr.add_str("env_name")("Name of the environment to remove")
    psr.add_str("--dir", dest="env_dir")("Environments root dir")
    psr.add_str("pkg_name")("package to update")

    comp.run()
