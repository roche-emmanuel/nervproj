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

        proj_path = self.get_root_dir()

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

        proj_path = None
        def_paths = self.ctx.get_config().get("project_paths", [])

        all_paths = [self.get_path(base_path, proj_name) for base_path in def_paths
                     for proj_name in self.desc['names']]

        if 'paths' in self.desc:
            all_paths = self.desc['paths'] + all_paths

        proj_path = self.ctx.select_first_valid_path(all_paths)

        pname = self.get_name()
        assert proj_path is not None, f"No valid path for project '{pname}'"

        # Return that project path:
        return proj_path

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

    def get_component(self, cname):
        """Retrieve a given component in this project"""
        return self.components[cname]
