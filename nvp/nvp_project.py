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

        # We might have some "scripts" already registered for that project from the desc:
        self.scripts = self.desc.get("scripts", {})

        proj_path = self.get_root_dir()

        if proj_path is not None:
            # Load the additional project config elements:
            cfg_file = self.get_path(proj_path, "nvp_config.json")
            if self.file_exists(cfg_file):
                self.config = self.read_json(cfg_file)

            # Update the scripts from what we just read from the config:
            self.scripts.update(self.config.get("scripts", {}))

            if self.file_exists(proj_path, "nvp_plug.py"):
                # logger.info("Loading NVP plugin from %s...", proj_name)
                sys.path.insert(0, proj_path)
                plug_module = import_module("nvp_plug")
                plug_module.register_nvp_plugin(ctx, self)
                sys.path.pop(0)
                # Remove the module name from the list of loaded modules:
                del sys.modules["nvp_plug"]

    def has_name(self, pname):
        """Check if this project has the given name"""
        return pname in self.desc['names']

    def get_root_dir(self):
        """Search for the location of a project given its name"""
        if self.root_dir is not None:
            return self.root_dir

        proj_path = None
        def_paths = self.ctx.get_config().get("project_paths", [])
        

        # all_paths = [self.get_path(base_path, proj_name) for base_path in def_paths
        #              for proj_name in self.desc['names']]
        all_paths = [self.get_path(base_path, self.get_name(False)) for base_path in def_paths]

        if 'paths' in self.desc:
            all_paths = self.desc['paths'] + all_paths

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
        return self.desc['repository_url']

    def get_name(self, to_lower=True):
        """Retrieve the canonical project name"""
        if to_lower:
            return self.desc['names'][0].lower()
        return self.desc['names'][0]

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

    def run_script(self, script_name):
        """Run a given script given by name if available"""

        # get the script from the config:
        if not script_name in self.scripts:
            logger.warning("No script named %s in project %s", script_name, self.get_name())
            return

        # otherwise we get the script command and cwd:
        script = self.scripts[script_name]
        cmd = script['cmd']
        cmd = cmd.replace("${PROJECT_ROOT_DIR}", self.get_root_dir())

        cwd = script.get('cwd', None)
        if cwd is not None:
            # Ensure that we replace the path variables:
            cwd = cwd.replace("${PROJECT_ROOT_DIR}", self.get_root_dir())

        # Execute that command:
        logger.debug("Executing script command: %s (cwd=%s)", cmd, cwd)
        self.execute(cmd, cwd=cwd)
