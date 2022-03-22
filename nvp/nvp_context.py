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
            home_drive = os.getenv("HOMEDRIVE")
            home_path = os.getenv("HOMEPATH")
            assert home_drive is not None and home_path is not None, "Invalid home drive or path"
            self.home_dir = home_drive+home_path

        # Load the manager config:
        self.load_config()

        self.components = {}
        self.projects = []

        self.flavor = None
        self.platform = None

        pname = sys.platform
        if pname.startswith('win32'):
            self.flavor = "msvc64"
            self.platform = "windows"
        elif pname.startswith('linux'):
            self.flavor = 'linux64'
            self.platform = "linux"

        assert self.platform in ["windows", "linux"], f"Unsupported platform {pname}"

        self.parsers = None
        self.sub_parsers = {}
        self.setup_parsers()

        self.load_projects()

        self.settings = vars(self.parsers['main'].parse_args())

        self.flavor = self.settings.get("flavor", self.flavor)
        logger.debug("Using flavor %s", self.flavor)

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

    def setup_parsers(self):
        """Setup the command line parsers to use in this context"""

        parser = argparse.ArgumentParser()

        # cf. https://stackoverflow.com/questions/15301147/python-argparse-default-value-or-specified-value
        parser.add_argument("--check-deps", dest='check_deps', nargs='?', type=str, const="all",
                            help="Check and build the dependencies required for NervProj")
        parser.add_argument("--rebuild", dest='rebuild', action='store_true',
                            help="Force rebuilding from sources")
        parser.add_argument("--install-python-requirements", dest='install_python_requirements', action='store_true',
                            help="Install the requirements for the python env.")
        parser.add_argument("-v", "--verbose", dest='verbose', action='store_true',
                            help="Enable display of verbose debug outputs.")
        parser.add_argument("-p", "--project", dest='project', type=str, default="none",
                            help="Select the current sub-project")

        parser_desc = {
            "home": None,
            "get_dir": None,
            "admin": {
                "install-cli": None
            },
            "tools": {'install': None},
            "milestone": {"add": None, "list": None, "close": None},
        }

        self.parsers = {'main': parser}

        self.define_subparsers("main", parser_desc)
        psr = self.parsers['main.get_dir']
        psr.add_argument("-p", "--project", dest='project', type=str, default="none",
                         help="Select the current sub-project")

        psr = self.parsers['main.milestone.add']
        psr.add_argument("-p", "--project", dest='project', type=str, default="none",
                         help="Select the current sub-project")
        psr.add_argument("-t", "--title", dest='title', type=str,
                         help="Title for the new milestone")
        psr.add_argument("-d", "--desc", dest='description', type=str,
                         help="Description for the new milestone")
        psr.add_argument("-s", "--start", dest='start_date', type=str,
                         help="Start date for the new milestone")
        psr.add_argument("-e", "--end", dest='end_date', type=str,
                         help="End date for the new milestone")

        psr = self.parsers['main.milestone.list']
        psr.add_argument("-t", "--title", dest='title', type=str,
                         help="Title of the listed milestone")

        psr = self.parsers['main.milestone.close']
        psr.add_argument("-t", "--title", dest='title', type=str,
                         help="Title for the milestone to close")
        psr.add_argument("--id", dest='milestone_id', type=int,
                         help="ID for the milestone to close")

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
            self.config.update(user_cfg)

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

    def is_windows(self):
        """Return true if this is a windows platform"""
        return self.platform == "windows"

    def is_linux(self):
        """Return true if this is a linux platform"""
        return self.platform == "linux"

    def get_flavor(self):
        """Retrieve the current flavor"""
        return self.flavor

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

    def register_component(self, cname, comp):
        """Register a component with a given name"""
        self.components[cname] = comp

    def get_component(self, cname):
        """Retrieve a component by name or create it if missing"""

        proj = self.get_current_project()
        if proj.has_component(cname):
            return proj.get_component(cname)

        if cname in self.components:
            return self.components[cname]

        # logger.info("Component list: %s", self.components.keys())
        # logger.info("proj_comp_name: %s", proj_comp_name)
        # Search for that component in the component paths:
        cpaths = [self.get_path(self.get_root_dir(), "nvp", "components")] + sys.path
        cfiles = [self.get_path(base_dir, f"{cname}.py") for base_dir in cpaths]

        comp_path = self.select_first_valid_path(cfiles)
        if comp_path is None:
            # logger.warning("No path found for %s in %s", cname, cfiles)
            return None

        logger.info("Loading component %s from %s", cname, comp_path)
        base_dir = os.path.dirname(comp_path)
        # if not base_dir in sys.path:
        #     logger.debug("Adding %s to python sys.path", base_dir)

        sys.path.insert(0, base_dir)
        comp_module = import_module(cname)
        comp_module.register_component(self)
        sys.path.pop(0)

        # Should now have the component name in the dict:
        assert cname in self.components, f"Could not register component for {cname}"
        return self.components[cname]

    def get_current_project(self):
        """Retrieve the project details."""

        pname = self.settings['project']

        return self.get_project(pname)

    def run(self):
        """Run this context."""
        l0_cmd = self.settings['l0_cmd']

        comp = None
        if l0_cmd == 'get_dir':
            comp = self.get_component('gitlab')

        if l0_cmd == 'admin':
            comp = self.get_component('admin')

        if l0_cmd == 'tools':
            comp = self.get_component('build')

        if l0_cmd == 'milestone':
            comp = self.get_component('gitlab')

        if comp is None:
            comp = self.get_component(l0_cmd)

        if comp is not None:
            comp.process_command()
        else:
            logger.warning("No component available to process '%s'", l0_cmd)

    def load_projects(self):
        """Load the plugins from the sub-project if any"""

        for pdesc in self.config.get("projects", []):
            proj = NVPProject(pdesc, self)
            self.projects.append(proj)
