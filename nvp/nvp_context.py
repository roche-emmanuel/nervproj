"""NVP context class"""
import logging
import os
import sys
import argparse
from importlib import import_module

from nvp.nvp_object import NVPObject
from nvp.nvp_project import NVPProject

logger = logging.getLogger(__name__)


class NVPContext(NVPObject):
    """Main NVP context class"""

    def __init__(self):
        """Initialize the NVP context."""

        verbose = os.getenv("NVP_VERBOSE", '0')
        lvl = logging.DEBUG if verbose == '1' else logging.INFO
        # print("Sys args: %s" % sys.argv)
        if sys.argv[1] == "get_dir":
            lvl = logging.ERROR

        logging.basicConfig(stream=sys.stdout, level=lvl,
                            format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                            datefmt='%Y/%m/%d %H:%M:%S')

        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.abspath(os.path.join(self.root_dir, os.pardir))

        # Also retrieve the home directory here:
        self.home_dir = os.getenv("HOME")
        if self.home_dir is None:
            # We could be in a windows batch environment here:
            self.home_dir = self.get_win_home_dir()

        # Load the manager config:
        self.load_config()

        self.components = {}
        self.projects = []

        self.platform = None

        pname = sys.platform
        if pname.startswith('win32'):
            self.platform = "windows"
        elif pname.startswith('linux'):
            self.platform = "linux"

        assert self.platform in ["windows", "linux"], f"Unsupported platform {pname}"

        # Check if we are in a cygwin env:
        self.cyg_home_dir = None
        if self.platform == "windows":
            self.cyg_home_dir = self.to_cygwin_path(self.home_dir)

        if self.cyg_home_dir is not None:
            logger.debug("Cygwin home dir is: %s", self.cyg_home_dir)

        self.setup_paths()

        self.parsers = None
        self.sub_parsers = {}
        self.setup_parsers()

        self.load_default_components()

        self.load_projects()

        self.settings = vars(self.parsers['main'].parse_args())

    def define_subparsers(self, pname, desc):
        """define subparsers recursively."""

        parent = self.parsers[pname]

        # level is the number of '.' we have in the parent parser name:
        lvl = pname.count('.')

        if pname not in self.sub_parsers:
            self.sub_parsers[pname] = parent.add_subparsers(title=f'Level{lvl} commands',
                                                            dest=f'l{lvl}_cmd',
                                                            description=f'Available level{lvl} commands below:',
                                                            help=f'Level{lvl} commands additional help')

        subparsers = self.sub_parsers[pname]

        for key, sub_desc in desc.items():
            # logger.info("Adding parser for %s", key)
            ppp = subparsers.add_parser(key)
            sub_name = f"{pname}.{key}"
            assert sub_name not in self.parsers, f"Parser {sub_name} already defined."

            self.parsers[sub_name] = ppp

            # Check if we have more sub parsers:
            if sub_desc is not None:
                self.define_subparsers(sub_name, sub_desc)

        return self.parsers

    def setup_paths(self):
        """Setup the paths that will be used during build or run process."""

        # Store the deps folder:
        base_dir = self.get_root_dir()
        self.tools_dir = self.get_path(base_dir, "tools", self.platform)

    def setup_parsers(self):
        """Setup the command line parsers to use in this context"""

        parser = argparse.ArgumentParser()

        # cf. https://stackoverflow.com/questions/15301147/python-argparse-default-value-or-specified-value
        parser.add_argument("-v", "--verbose", dest='verbose', action='store_true',
                            help="Enable display of verbose debug outputs.")
        parser.add_argument("-p", "--project", dest='project', type=str, default="none",
                            help="Select the current sub-project")

        self.parsers = {'main': parser}

    def get_parser(self, name):
        """Retrieve a parser by name"""
        return self.parsers[name]

    def has_parser(self, name):
        """Check if a given parser is already created."""
        return name in self.parsers

    def load_config(self):
        """Load the config.json file, can only be done after we have the root path."""

        cfgfile = self.get_path(self.root_dir, "config.json")
        self.config = self.read_json(cfgfile)
        logger.log(0, "Loaded config: %s", self.config)

        # Apply config override if any:
        # First we should retrieve the list of potential paths for that file:
        cfg_paths = self.config.get("user_config_urls", ["${NVP_DIR}/config.user.json"])
        cfg_file = self.select_first_valid_path(cfg_paths)

        if cfg_file is not None:
            user_cfg = self.read_json(cfg_file)

            # If a key starts with a "+" symbol then we append to the existing element instead of overriding it:
            for key, val in user_cfg.items():
                if key[0] == "+":
                    # Should append here:
                    key = key[1:]
                    if key in self.config:
                        # Should have the same types:
                        assert type(self.config[key]) == type(val), f"Type mismatch on config key {key}"
                        if isinstance(self.config[key], list):
                            self.config[key] += val
                        else:
                            # assume that we have a dict:
                            self.config[key].update(val)
                    else:
                        # add the new key value:
                        self.config[key] = val
                else:
                    # regular keys:
                    self.config[key] = val

            # self.config.update(user_cfg)

    def has_project(self, pname):
        """Check if a given project should be considered available"""
        for proj in self.projects:
            if proj.has_name(pname):
                return True

        return False

    def get_project(self, pname):
        """Retrieve a project by name."""
        for proj in self.projects:
            if proj.has_name(pname):
                return proj

        return None

    def is_cygwin(self):
        """Check if we are running from cygwin environment."""
        return self.cyg_home_dir is not None

    def get_platform(self):
        """Retrieve the current platform"""
        return self.platform

    def get_root_dir(self):
        """Retrieve the root directory of the NVP project"""
        return self.root_dir

    def get_home_dir(self):
        """retrieve the home directory"""
        return self.home_dir

    def get_config(self):
        """retrieve the global config object"""
        return self.config

    def get_settings(self):
        """Retrieve the input settings used to created this context"""
        return self.settings

    def select_first_valid_path(self, allpaths):
        """Select the first valid path in a given list.
        The list may also contain URLs. May return None if no valid path is found."""

        for pname in allpaths:
            logger.debug("Checking path %s", pname)
            # Replace the variables if any:
            pname = pname.replace("${NVP_DIR}", self.root_dir)
            pname = pname.replace("${HOME}", self.home_dir)

            if (pname.startswith("http://") or pname.startswith("https://")) and self.is_downloadable(pname):
                # URL resource is downloadable:
                return pname

            # check elf.pif the path is valid:
            if self.path_exists(pname):
                return pname

        return None

    def load_default_components(self):
        """Load the default components available in this project"""
        comp_path = self.get_path(self.get_root_dir(), "nvp", "components")

        # Get all .py files in that folder:
        comp_files = self.get_all_files(comp_path, "\\.py$")
        logger.debug("Found Component files: %s", comp_files)

        # load those components:
        # sys.path.insert(0, comp_path)

        for comp in comp_files:
            mod_name = f"nvp.components.{comp[:-3]}"
            comp_module = import_module(mod_name)
            comp_module.register_component(self)

        # sys.path.pop(0)

    def register_component(self, cname, comp):
        """Register a component with a given name"""
        self.components[cname] = comp

    def get_component(self, cname, do_init=True):
        """Retrieve a component by name or create it if missing"""

        proj = self.get_current_project()
        if proj is not None and proj.has_component(cname):
            return proj.get_component(cname, do_init)

        if cname in self.components:
            comp = self.components[cname]
            if do_init:
                comp.initialize()
            return comp

        logger.warning("Cannot find component %s", cname)

        # # logger.info("Component list: %s", self.components.keys())
        # # logger.info("proj_comp_name: %s", proj_comp_name)
        # # Search for that component in the component paths:
        # cpaths = [self.get_path(self.get_root_dir(), "nvp", "components")] + sys.path
        # cfiles = [self.get_path(base_dir, f"{cname}.py") for base_dir in cpaths]

        # comp_path = self.select_first_valid_path(cfiles)
        # if comp_path is None:
        #     # logger.warning("No path found for %s in %s", cname, cfiles)
        #     return None

        # logger.info("Loading component %s from %s", cname, comp_path)
        # base_dir = os.path.dirname(comp_path)
        # # if not base_dir in sys.path:
        # #     logger.debug("Adding %s to python sys.path", base_dir)

        # sys.path.insert(0, base_dir)
        # comp_module = import_module(cname)
        # comp_module.register_component(self)
        # sys.path.pop(0)

        # # Should now have the component name in the dict:
        # assert cname in self.components, f"Could not register component for {cname}"
        # return self.components[cname]

    def get_current_project(self):
        """Retrieve the project details."""

        pname = self.settings['project']

        return self.get_project(pname)

    def get_command(self, lvl):
        """Retrieve the command at a given level"""
        return self.settings.get(f"l{lvl}_cmd", None)

    def run(self):
        """Run this context."""
        cmd = self.get_command(0)

        proj = self.get_current_project()
        if proj is not None and proj.process_command(cmd):
            return

        for _, comp in self.components.items():
            if comp.process_command(cmd):
                return

        logger.warning("No component available to process '%s'", cmd)

    def load_projects(self):
        """Load the plugins from the sub-project if any"""

        for pdesc in self.config.get("projects", []):
            proj = NVPProject(pdesc, self)
            self.projects.append(proj)
