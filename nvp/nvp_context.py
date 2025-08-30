"""NVP context class"""

# import signal
import argparse
import logging
import os
import platform
import re
import signal
import sys
from importlib import import_module

from nvp.nvp_object import NVPCheckError, NVPObject
from nvp.nvp_project import NVPProject

logger = logging.getLogger(__name__)


# def signal_handler(_sig, _frame):
#     """Handler for ctrl+c signal"""
#     logger.info("NVPContext: Ctrl+C pressed, exiting.")
#     sys.exit(0)


# signal.signal(signal.SIGINT, signal_handler)


class ParserContext(object):
    """Simple class used to setup an argparse parser conviniently"""

    def __init__(self, parser, pname):
        """Start with a parser to add arguments on it"""
        self.parser = parser
        self.pname = pname
        self.cur_state = None

    def __del__(self):
        """Destructor for this parser context"""
        if self.cur_state is not None:
            raise NVPCheckError(f"Parser context for {self.pname} was not closed properly.")

    def end(self):
        """Finish the current argument"""
        if self.cur_state is not None:
            args = self.cur_state["args"]
            del self.cur_state["args"]
            self.parser.add_argument(*args, **self.cur_state)
            self.cur_state = None

    def add_str(self, *args, **kwargs):
        """Add a string argument"""
        # finish previous arg if any:
        self.end()

        self.cur_state = {"args": args, "type": str}
        self.cur_state.update(kwargs)
        return self

    def add_int(self, *args, **kwargs):
        """Add an int argument"""
        # finish previous arg if any:
        self.end()

        self.cur_state = {"args": args, "type": int}
        self.cur_state.update(kwargs)
        return self

    def add_float(self, *args, **kwargs):
        """Add a float argument"""
        # finish previous arg if any:
        self.end()

        self.cur_state = {"args": args, "type": float}
        self.cur_state.update(kwargs)
        return self

    def add_flag(self, *args, **kwargs):
        """Add a flag argument"""
        # finish previous arg if any:
        self.end()

        self.cur_state = {"args": args, "action": "store_true"}
        self.cur_state.update(kwargs)
        return self

    def __call__(self, desc=None, **kwargs):
        """Add elements and finish the arg."""
        if desc is not None:
            self.cur_state["help"] = desc
        self.cur_state.update(kwargs)
        self.end()


class NVPContext(NVPObject):
    """Main NVP context class"""

    instance = None

    def __init__(self, base_dir=None, is_main=False):
        """Initialize the NVP context."""

        assert NVPContext.instance is None, "NVPContext already initialized."

        NVPContext.instance = self

        verbose = os.getenv("NVP_VERBOSE", "0")
        lvl = logging.DEBUG if verbose == "1" else logging.INFO
        # print("Sys args: %s" % sys.argv)
        if len(sys.argv) >= 2 and sys.argv[1] == "get_dir":
            lvl = logging.ERROR

        logging.basicConfig(
            stream=sys.stdout,
            level=lvl,
            # format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="%Y/%m/%d %H:%M:%S",
        )

        self.is_master = is_main

        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.abspath(os.path.join(self.root_dir, os.pardir))

        # Store the current working directory:
        self.base_dir = self.get_cwd() if base_dir is None else base_dir
        # logger.info("Context base dir: %s", self.base_dir)

        # Also retrieve the home directory here:
        self.home_dir = os.getenv("HOME")
        if self.home_dir is None:
            # We could be in a windows batch environment here:
            self.home_dir = self.get_win_home_dir()

        # Load the manager config:
        self.load_config()

        self.construct_frames = []
        self.components = {}
        self.projects = []

        self.handlers = {}
        self.handler_hashes = {}

        self.platform = None
        self.commands = None

        pname = sys.platform
        if pname.startswith("win32"):
            self.platform = "windows"
        elif pname.startswith("linux"):
            arch = platform.machine()
            if arch == "aarch64":
                self.platform = "raspberry64"
            elif arch == "armv7l":
                self.platform = "raspberry"
            else:
                self.platform = "linux"

        assert self.platform in ["windows", "linux", "raspberry", "raspberry64"], f"Unsupported platform {pname}"

        # Check if we are in a cygwin env:
        self.cyg_home_dir = None
        if self.platform == "windows":
            self.cyg_home_dir = self.to_cygwin_path(self.home_dir)

        if self.cyg_home_dir is not None:
            logger.debug("Cygwin home dir is: %s", self.cyg_home_dir)

        self.setup_paths()

        self.parsers = None
        self.settings = {}
        self.additional_args = None

        self.sub_parsers = {}
        self.setup_parsers(is_main)

        if is_main:
            self.load_default_components()

        self.load_projects()

    @property
    def is_raspberry(self):
        """check if we are on raspberry"""
        return self.platform == "raspberry"

    @property
    def is_raspberry64(self):
        """check if we are on raspberry64"""
        return self.platform == "raspberry64"

    @staticmethod
    def get(create=False):
        """Return instance of this class"""
        if create and NVPContext.instance is None:
            NVPContext()

        assert NVPContext.instance is not None, "NVPContext not created yet."
        return NVPContext.instance

    def define_subparsers(self, pname, desc):
        """define subparsers recursively."""

        # If desc is a list then we convert that to a dict with None values:
        if isinstance(desc, list):
            desc = {key: None for key in desc}

        parent = self.parsers[pname]

        # level is the number of '.' we have in the parent parser name:
        lvl = pname.count(".")

        if pname not in self.sub_parsers:
            self.sub_parsers[pname] = parent.add_subparsers(
                title=f"Level{lvl} commands",
                dest=f"l{lvl}_cmd",
                description=f"Available level{lvl} commands below:",
                help=f"Level{lvl} commands additional help",
            )

        subparsers = self.sub_parsers[pname]

        for key, sub_desc in desc.items():
            # logger.info("Adding parser for %s", key)
            # The key may contain a point, in which case we should split it here:
            if "." in key:
                parts = key.split(".", 1)
                key = parts[0]
                sub_desc = {parts[1]: sub_desc}

            sub_name = f"{pname}.{key}"

            if sub_name not in self.parsers:
                ppp = subparsers.add_parser(key)
                self.parsers[sub_name] = ppp

            # No error if the parser is already registered:
            # assert sub_name not in self.parsers, f"Parser {sub_name} already defined."

            # Check if we have more sub parsers:
            if sub_desc is not None:
                self.define_subparsers(sub_name, sub_desc)

        return self.parsers

    def setup_paths(self):
        """Setup the paths that will be used during build or run process."""

        # Store the deps folder:
        base_dir = self.get_root_dir()
        self.tools_dir = self.get_path(base_dir, "tools", self.platform)

    def setup_parsers(self, is_main):
        """Setup the command line parsers to use in this context"""

        parser = argparse.ArgumentParser()

        # cf. https://stackoverflow.com/questions/15301147/python-argparse-default-value-or-specified-value
        parser.add_argument(
            "-v", "--verbose", dest="verbose", action="store_true", help="Enable display of verbose debug outputs."
        )
        if is_main:
            parser.add_argument("-p", "--project", dest="project", type=str, help="Select the current sub-project")

        self.parsers = {"main": parser}

        if is_main:
            self.define_subparsers("main", ["get_dir", "list-scripts"])
            psr = self.get_parser("main.get_dir")
            psr.add_argument("-p", "--project", dest="project", type=str, help="Select the current sub-project")

    def build_parser(self, pname, parent="main"):
        """Build a parser and return an associated parser context"""
        self.define_subparsers(parent, [pname])
        pname = f"{parent}.{pname}"
        psr = self.get_parser(pname)
        return ParserContext(psr, pname)

    def get_parser(self, name):
        """Retrieve a parser by name"""
        return self.parsers[name]

    def has_parser(self, name):
        """Check if a given parser is already created."""
        return name in self.parsers

    def extend_config(self, user_cfg):
        """Extend the current config with the user provided config"""

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

    def load_config(self):
        """Load the config.json file, can only be done after we have the root path."""

        # Check if we have a config.yml file:
        cfg_file = self.get_path(self.root_dir, "config.yml")
        self.check(self.file_exists(cfg_file), "Invalid config file %s", cfg_file)
        self.config = self.read_yaml(cfg_file)
        # else:
        #     # fallback to the config.json file:
        #     cfgfile = self.get_path(self.root_dir, "config.json")
        #     self.config = self.read_json(cfgfile)

        logger.log(0, "Loaded config: %s", self.config)

        # Apply config override if any:
        # Check if we have an $HOME/.nvp/config.yml file
        cfg_file = self.get_path(self.get_home_dir(), ".nvp", "config.yml")
        if self.file_exists(cfg_file):
            logger.debug("Loading user config from file %s", cfg_file)

            user_cfg = self.read_yaml(cfg_file)
            self.extend_config(user_cfg)

        # First we should retrieve the list of potential paths for that file:
        cfg_paths = self.config.get("user_config_urls", ["${NVP_DIR}/config.user.json"])
        # Use all the available user configs instead of just one:
        hlocs = {
            "${NVP_DIR}": self.root_dir,
            "${HOME}": self.home_dir,
        }

        for cfg_path in cfg_paths:
            cpath = self.fill_placeholders(cfg_path, hlocs)
            if self.file_exists(cpath):
                if self.get_path_extension(cpath) == ".json":
                    user_cfg = self.read_json(cpath)
                else:
                    user_cfg = self.read_yaml(cpath)
                self.extend_config(user_cfg)

        # cfg_file = self.select_first_valid_path(cfg_paths)

        # if cfg_file is not None:
        #     user_cfg = self.read_json(cfg_file)
        #     self.extend_config(user_cfg)

        # self.config.update(user_cfg)

    def get_known_vars(self):
        """Get all the known dirs variables."""
        hlocs = {
            "${NVP_DIR}": self.root_dir,
            "${HOME_DIR}": self.home_dir,
            "${BASE_DIR}": self.base_dir,
            "${HOSTNAME}": self.get_hostname().lower(),
            "${PLATFORM}": self.get_platform().lower(),
        }

        # Add the root dir from all known projects:
        for proj in self.get_projects():
            key = f"${{{proj.get_name().upper()}_DIR}}"
            val = proj.get_root_dir()
            if key not in hlocs:
                # self.info("Adding project dir: %s=%s", key, val)
                hlocs[key] = val

        return hlocs

    def resolve_path(self, path, check_resolved=True):
        """Fill placeholders in a path."""
        hlocs = self.get_known_vars()

        path = self.fill_placeholders(path, hlocs)

        if check_resolved:
            # Check that we have no remaining vars:
            pattern = r"\$\{([^}]+)\}"
            matches = re.findall(pattern, path)
            self.check(len(matches) == 0, "Found unresolved variables in path: %s", matches)

        return path

    def enable_process_restart(self):
        """Notify that we will want to restart the current process"""
        if not self.file_exists("nvp_no_restart"):
            self.write_text_file("", "nvp_restart_requested")

    def kill_process(self):
        """Kill the current process"""
        os.kill(os.getpid(), signal.SIGTERM)

    def restart_process(self):
        """restart the current process"""
        self.enable_process_restart()
        self.kill_process()

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

    def is_master_context(self):
        """Check if this configured as a master context"""
        return self.is_master

    def is_cygwin(self):
        """Check if we are running from cygwin environment."""
        return self.cyg_home_dir is not None

    def get_platform(self):
        """Retrieve the current platform"""
        return self.platform

    def get_base_dir(self):
        """Retrieve the base directory for this context.
        This is the current working dir at the time the context is created by default"""
        return self.base_dir

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

    def get_additional_args(self):
        """Retrieve additional args to a script if any"""
        return self.additional_args

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
        return comp

    def update_dynamic_components(self, comps):
        """Update the dict of dynamic components"""
        dyn_comps = self.config.get("components", {})
        dyn_comps.update(comps)
        self.config["components"] = dyn_comps

    def get_component(self, cname, do_init=True):
        """Retrieve a component by name or create it if missing"""

        proj = self.get_current_project()
        if proj is not None and proj.has_component(cname):
            return proj.get_component(cname, do_init)

        if cname in self.components:
            comp = self.components[cname]
            if do_init and not comp.is_initialized():
                comp.initialize()
            return comp

        # If the requested component is not found, then it might be a dynamic component:
        # So we search for it in our config:
        return self.create_component(cname, do_init=do_init)

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
        # sys.path.pop(0)

        # # Should now have the component name in the dict:
        # assert cname in self.components, f"Could not register component for {cname}"
        # return self.components[cname]

    def import_module(self, mname):
        """Import a given module and return it"""
        return import_module(mname)

    def create_component(self, cname, args=None, do_init=True):
        """Create a new dynamic component given it's name and optional arguments"""
        dyn_comps = self.config.get("components", {})

        if cname not in dyn_comps:
            logger.warning("Cannot find component %s", cname)
            return None

        # We have a dyn component module name, so we try to load it:
        mname = dyn_comps[cname]
        def_args = mname.split(":")
        mname = def_args.pop(0)
        logger.debug("Loading dynamic component %s from module %s", cname, mname)

        if args is None:
            args = def_args

        comp_module = import_module(mname)

        # Add a construct frame for this component:
        frame = {"component_name": cname, "module": mname, "args": args}
        self.construct_frames.append(frame)
        comp = comp_module.create_component(self)
        comp.set_construct_frame(frame)

        # Remove the construct frame:
        self.construct_frames.pop()

        # The component must be registered before it is initialized to avoid any circular
        # init loop:
        self.register_component(cname, comp)

        if do_init:
            comp.initialize()

        return comp

    def get_construct_frames(self):
        """Retrieve the current list of construct frames"""
        return self.construct_frames

    def get_construct_frame(self, idx=-1):
        """Retrieve a given construct frame"""
        return self.construct_frames[idx]

    def get_construct_args(self, idx=-1):
        """Retrieve the construct arguments from a given frame"""
        args = self.construct_frames[idx]["args"]
        if len(args) == 0:
            return None
        return args

    def get_current_project(self, resolve_cwd=False) -> NVPProject | None:
        """Retrieve the project details."""
        pname = self.settings.get("project", None)
        if pname is not None:
            return self.get_project(pname)

        if resolve_cwd:
            # Check the current project from the CWD:
            cwd = self.get_cwd()
            cwd = self.to_absolute_path(cwd)
            for proj in self.get_projects():
                ppath = self.to_absolute_path(proj.get_root_dir())
                # logger.error("Checking %s against %s", cwd, ppath)
                if cwd.startswith(ppath):
                    return proj

        return None

    def resolve_root_dir(self, project=None):
        """Resolve a root directory either from project or CWD"""
        if project is None:
            project = self.get_current_project(True)

        if project:
            return project.get_root_dir()

        # We might still be in the NVP project itself:
        cwd = self.to_absolute_path(self.get_cwd())

        root_dir = self.to_absolute_path(self.get_root_dir())
        if cwd.startswith(root_dir):
            return root_dir

        return None

    def process_get_dir(self):
        """Retrieve the root dir for a given sub project and
        return that path on stdout"""
        proj_dir = self.resolve_root_dir()

        if proj_dir is None:
            sys.stdout.write("No root dir found.")
            sys.stdout.flush()
            return

        if self.is_windows:
            proj_dir = self.to_cygwin_path(proj_dir)

        sys.stdout.write(proj_dir)
        sys.stdout.flush()

    def get_commands(self):
        """Get all the command elements"""
        if self.commands is None:
            self.commands = []
            lvl = 0
            while True:
                val = self.settings.get(f"l{lvl}_cmd", None)
                if val is not None:
                    self.commands.append(val)
                    lvl += 1
                else:
                    break

        return self.commands

    def get_command(self, lvl):
        """Retrieve the command at a given level"""
        cmds = self.get_commands()
        return cmds[lvl] if lvl < len(cmds) else None

    def get_command_path(self):
        """Return the full command path"""
        cmds = self.get_commands()
        return ".".join(cmds)

    def parse_args(self, allow_additionals):
        """Parse the command line arguments"""
        # cf. https://docs.python.org/3.4/library/argparse.html#partial-parsing
        if allow_additionals:
            # before starting the regular parsing, we check if the first argument is a script name,
            # in which case we should caller the runner directly with the remaining args.
            if len(sys.argv) >= 2:
                script_name = sys.argv[1]
                self.settings = {}
                runner = self.get_component("runner")
                if runner.has_script(script_name):
                    # This is a valid script name, so we should add the "run" command
                    # before this script name:
                    sys.argv.insert(1, "run")

            # logger.info("Parsing args: %s", sys.argv)
            self.settings, self.additional_args = self.parsers["main"].parse_known_args()
            self.settings = vars(self.settings)
            # logger.info("Got settings: %s", self.settings)
            # logger.info("Got additional args: %s", self.additional_args)
        else:
            self.settings = vars(self.parsers["main"].parse_args())

    def run(self):
        """Run this context."""
        # We allow additional args by default if this is the master context:
        self.parse_args(self.is_master)

        cmd = self.get_command(0)

        if cmd == "get_dir":
            self.process_get_dir()
            return

        if cmd == "list-scripts":
            runner = self.get_component("runner")
            runner.list_scripts()
            return

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
            self.add_project(proj)

    def add_project(self, proj):
        """Add a project to the list"""
        self.projects.append(proj)

    def get_projects(self):
        """Retrieve the list of available projects"""
        return self.projects

    def resolve_module_file(self, hname):
        """Resolve a file path for a given python module name"""
        sep = "\\" if self.is_windows else "/"

        hfile = hname.replace(".", sep) + ".py"

        for base_path in sys.path:
            filepath = self.get_path(base_path, hfile)
            if self.file_exists(filepath):
                return filepath

        self.throw("Cannot resolve file for module %s", hname)

    def get_handler(self, hname):
        """Get a handler by name"""

        # Adding support for hot reloading of handlers here:
        # Given a module name, we should try to find the corresponding file:
        filepath = self.resolve_module_file(hname)

        # Compute the hash of that file:
        fhash = self.compute_file_hash(filepath)
        prev_hash = self.handler_hashes.get(filepath, None)
        if prev_hash is not None and prev_hash != fhash:
            logger.debug("Detected change in %s, reloading handler %s", filepath, hname)

            # Remove the already loaded function:
            self.check(hname in self.handlers, "Expected handler to be loader already: %s", hname)
            del self.handlers[hname]

        # Store the new file hash anyway:
        self.handler_hashes[filepath] = fhash

        if hname in self.handlers:
            return self.handlers[hname]

        # otherwise we have to search for that handler:
        comp_module = import_module(hname)
        handler = comp_module.handle
        del sys.modules[hname]

        self.handlers[hname] = handler
        return handler

    def call_handler(self, hname, *args, **kwargs):
        """Call a given handler with arguments"""
        handler = self.get_handler(hname)
        return handler(*args, **kwargs)

    def resolve_object(self, container, key, hlocs=None):
        """Resolve an object with either a platform or host suffix"""
        hname = self.get_hostname().lower()
        key2 = f"{key}.{self.get_platform()}"
        key3 = f"{key}.{hname}"

        desc = None
        desc = container.get(key, None)

        if key2 in container:
            if desc is None:
                desc = container[key2]
            elif isinstance(desc, dict):
                desc.update(container[key2])
            else:
                desc = container[key2]

        if key3 in container:
            if desc is None:
                desc = container[key3]
            elif isinstance(desc, dict):
                desc.update(container[key3])
            else:
                desc = container[key3]

        if hlocs is not None:
            desc = self.fill_placeholders(desc, hlocs)

        return desc
