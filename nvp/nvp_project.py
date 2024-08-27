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

        proj_path = self.get_root_dir()

        # dir0 = self.config.get("parent_root_dir", "parent")
        # dir1 = self.config.get("project_root_dir", "proj")
        is_local_sub_proj = self.config.get("is_sub_project", False)

        if proj_path is not None:
            # Load the additional project config elements:
            cfg_file = self.get_path(proj_path, "nvp_config.json")
            if self.file_exists(cfg_file) and not is_local_sub_proj:
                # logger.warning("Ignoring project config file %s", cfg_file)
                self.config.update(self.read_json(cfg_file))

            # Prefer the yaml config if available:
            cfg_file = self.get_path(proj_path, "nvp_config.yml")
            if self.file_exists(cfg_file) and not is_local_sub_proj:
                cfg = self.read_yaml(cfg_file)
                # logger.info("Project %s config: %s", self.get_name(False), cfg)
                self.config.update(cfg)

            # Note: the nvp_plug system bellow is obsolete and should be removed eventually:
            if ctx.is_master_context() and self.file_exists(proj_path, "nvp_plug.py") and not is_local_sub_proj:
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

            # Check if we have subprojects:
            sub_projects = self.config.get("sub_projects", [])
            for sproj_cfg in sub_projects:
                # check if this is an absolute path:

                if not self.is_absolute_path(sproj_cfg):
                    # Prepend this project path:
                    sproj_cfg = self.get_path(proj_path, sproj_cfg)

                if not self.file_exists(sproj_cfg):
                    logger.info("Ignoring missing sub_project at %s", sproj_cfg)
                    continue

                # Read that config file:
                scfg = self.read_yaml(sproj_cfg)

                scfg["parent_root_dir"] = proj_path

                # Ensure we have the project_root_dir set in that config:
                if "project_root_dir" in scfg:
                    sub_root_dir = scfg.get("project_root_dir", proj_path)

                    # Replace the placeholder as needed:
                    hlocs = {"${PARENT_ROOT_DIR}": proj_path}
                    sub_root_dir = self.fill_placeholders(sub_root_dir, hlocs)
                    scfg["project_root_dir"] = sub_root_dir
                    logger.info("Found project root dir for %s: %s", scfg["names"][0], sub_root_dir)

                if "names" not in scfg:
                    # Add the names from the parent project:
                    scfg["names"] = self.config["names"]

                # if we had no project root dir in the config then we can build one using the provided project names:
                if "project_root_dir" not in scfg:
                    logger.info("Searching project root dir for %s", scfg["names"][0])
                    proj_dir = self.find_project_folder(scfg["names"][0])
                    if proj_dir is None:
                        # Use our parent project path as fallback:
                        logger.info("Using default parent dir for sub proj %s: %s", scfg["names"][0], proj_path)
                        proj_dir = proj_path

                    # Assign parent path as root path:
                    scfg["project_root_dir"] = proj_dir

                scfg["is_sub_project"] = True

                # logger.info("Should load sub project from %s", sproj_cfg)
                sproj = NVPProject(scfg, self.ctx)
                self.ctx.add_project(sproj)

        # Get the script parameters:
        params = self.get_script_parameters()

        # Fill all the placeholders in the config:
        hlocs = {f"${{{key}}}": val for key, val in params.items()}
        hlocs["${PROJECT_ROOT_DIR}"] = self.get_root_dir()

        pdir = self.config.get("parent_root_dir", None)
        if pdir is not None and "${PARENT_ROOT_DIR}" not in hlocs:
            hlocs["${PARENT_ROOT_DIR}"] = pdir

        self.config = self.fill_placeholders(self.config, hlocs)

        # Keep track of the scripts:
        self.scripts = self.config.get("scripts", {})

    def has_name(self, pname):
        """Check if this project has the given name"""
        return pname in self.desc["names"]

    def find_project_folder(self, pname, additional_paths=None):
        """Find a project folder using all the available names for that project"""

        def_paths = self.ctx.get_config().get("project_paths", [])

        all_paths = [self.get_path(base_path, pname) for base_path in def_paths]

        if additional_paths is not None:
            all_paths = additional_paths + all_paths

        # logger.info("Checking all project paths: %s", all_paths)
        return self.ctx.select_first_valid_path(all_paths)

    def get_root_dir(self):
        """Search for the location of a project given its name"""
        if self.root_dir is not None:
            return self.root_dir

        if "project_root_dir" in self.config:
            self.root_dir = self.config["project_root_dir"]
            logger.info("Using custom subproject root dir: %s", self.root_dir)
            return self.root_dir

        proj_path = self.find_project_folder(self.get_name(False), self.desc.get("paths", None))

        # Actually the project path might be "None" if it is not available yet:
        # pname = self.get_name()
        # assert proj_path is not None, f"No valid path for project '{pname}'"
        if proj_path is None:
            logger.debug("No valid path found for project %s", self.get_name())

        self.root_dir = proj_path

        # Return that project path:
        return proj_path

    def auto_git_sync(self):
        """check if auto pull/push is supported"""
        return self.config.get("auto_git_sync", True)

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

    def get_script_names(self):
        """Retrieve the list of script names available in this project"""
        return list(self.scripts.keys())

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

    def get_script_parameters(self):
        """Get the script parameters in this project"""

        params = self.ctx.resolve_object(self.config, "script_parameters")

        hlocs = {
            "${PROJECT_ROOT_DIR}": self.get_root_dir(),
        }

        pdir = self.config.get("parent_root_dir", None)
        if pdir is not None:
            hlocs["${PARENT_ROOT_DIR}"] = pdir

        desc = {}
        if params is not None:
            for key, val in params.items():
                hlocs[f"${{{key}}}"] = val

            for pname, pvalue in params.items():
                desc[pname] = self.fill_placeholders(pvalue, hlocs)

        return desc

    def get_parameter(self, pname, hlocs=None):
        """Resolve a parameter by name"""
        res = self.ctx.resolve_object(self.config, pname)
        if hlocs is None:
            return res

        return self.fill_placeholders(res, hlocs)
