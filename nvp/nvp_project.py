"""NVP project class"""
import logging
import sys
from importlib import import_module

from nvp.nvp_object import NVPObject

logger = logging.getLogger(__name__)


class NVPProject(NVPObject):
    """Main NVP context class"""

    def __init__(self, desc, ctx):
        """Initialize the NVP project"""
        self.ctx = ctx
        self.desc = desc
        assert desc is not None, "Invalid project description."

        self.components = {}
        self.config = {}
        self.root_dir = None

        self.config.update(desc)

        # We might have some "scripts" already registered for that project from the desc:
        self.scripts = self.desc.get("scripts", {})

        proj_path = self.get_root_dir()

        if proj_path is not None:
            # Load the additional project config elements:
            cfg_file = self.get_path(proj_path, "nvp_config.json")
            if self.file_exists(cfg_file):
                self.config.update(self.read_json(cfg_file))

            # Prefer the yaml config if available:
            cfg_file = self.get_path(proj_path, "nvp_config.yml")
            if self.file_exists(cfg_file):
                cfg = self.read_yaml(cfg_file)
                # logger.info("Project %s config: %s", self.get_name(False), cfg)
                self.config.update(cfg)

            # Update the scripts from what we just read from the config:
            self.scripts.update(self.config.get("scripts", {}))

            # Note: the nvp_plug system bellow is obsolete and should be removed eventually:
            if ctx.is_master_context() and self.file_exists(proj_path, "nvp_plug.py"):
                # logger.info("Loading NVP plugin from %s...", proj_name)
                try:
                    sys.path.insert(0, proj_path)
                    plug_module = import_module("nvp_plug")
                    plug_module.register_nvp_plugin(ctx, self)
                    sys.path.pop(0)
                    # Remove the module name from the list of loaded modules:
                    del sys.modules["nvp_plug"]
                except ModuleNotFoundError as err:
                    logger.error("Cannot load project %s: exception: %s", self.get_name(False), str(err))

    def has_name(self, pname):
        """Check if this project has the given name"""
        return pname in self.desc["names"]

    def get_root_dir(self):
        """Search for the location of a project given its name"""
        if self.root_dir is not None:
            return self.root_dir

        proj_path = None
        def_paths = self.ctx.get_config().get("project_paths", [])

        # all_paths = [self.get_path(base_path, proj_name) for base_path in def_paths
        #              for proj_name in self.desc['names']]
        all_paths = [self.get_path(base_path, self.get_name(False)) for base_path in def_paths]

        if "paths" in self.desc:
            all_paths = self.desc["paths"] + all_paths

        # logger.info("Checking all project paths: %s", all_paths)
        proj_path = self.ctx.select_first_valid_path(all_paths)

        # Actually the project path might be "None" if it is not available yet:
        # pname = self.get_name()
        # assert proj_path is not None, f"No valid path for project '{pname}'"
        if proj_path is None:
            logger.debug("No valid path found for project %s", self.get_name())

        self.root_dir = proj_path

        # Return that project path:
        return proj_path

    def get_repository_url(self):
        """Retrieve the repository URL for that project"""
        return self.desc["repository_url"]

    def get_config(self):
        """Retrieve the configuration for this project"""
        return self.config

    def get_name(self, to_lower=True):
        """Retrieve the canonical project name"""
        if to_lower:
            return self.desc["names"][0].lower()
        return self.desc["names"][0]

    def register_component(self, cname, comp):
        """Register a project specific component"""
        self.components[cname] = comp

    def has_component(self, cname):
        """Check if this project has a given component"""
        return cname in self.components

    def get_component(self, cname, do_init=True):
        """Retrieve a given component in this project"""
        comp = self.components[cname]
        if do_init:
            comp.initialize()
        return comp

    def process_command(self, cmd):
        """Check if the components in this project can process the given command"""
        for _, comp in self.components.items():
            if comp.process_command(cmd) is not False:
                return True

        return False

    def get_dependencies(self):
        """Retrieve the list of dependencies declared for this project."""
        return self.config.get("dependencies", [])

    def get_script(self, script_name):
        """Retrieve a script desc by name"""
        desc = self.scripts.get(script_name, None)

        if desc is not None and desc.get("use_local_python", False):
            # Update the python path in the command
            plat = self.ctx.get_platform()
            key = f"{plat}_cmd"
            if key in desc:
                cmd = desc[key]
                # Remove the platform specific key value,
                # we will put that directly in the 'cmd' slot
                del desc[key]
            else:
                cmd = desc["cmd"]

            bdir = self.get_path(self.get_root_dir(), "tools", plat)
            folders = self.get_all_folders(bdir)
            pypath = None
            pdesc = self.ctx.get_component("tools").get_tool_desc("python")

            for fname in folders:
                if fname.startswith("python-"):
                    pydir = self.get_path(bdir, fname)
                    logger.debug("Using python install dir %s", pydir)
                    pypath = self.get_path(pydir, pdesc["sub_path"])
                    break

            assert pypath is not None, f"Cannot find local python path in project {self.get_name()}"
            cmd = cmd.replace("${PYTHON}", pypath)
            desc["cmd"] = cmd

        return desc

    def get_custom_python_env(self, env_name):
        """Try to retrieve a custom python env from this project"""
        all_envs = self.config.get("custom_python_envs", {})
        return all_envs.get(env_name, None)

    def get_nodejs_env(self, env_name):
        """Try to retrieve a custom nodejs env from this project"""
        all_envs = self.config.get("nodejs_envs", {})
        return all_envs.get(env_name, None)
