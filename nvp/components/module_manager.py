"""ModuleManager module"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = ModuleManager(ctx)
    ctx.register_component('module', comp)


class ModuleManager(NVPComponent):
    """Project command manager class"""

    def __init__(self, ctx: NVPContext):
        """Project commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        desc = {
            "mods": {"build": None, "install": None}
        }

        self.modules = None
        self.builder = None
        self.build_dir = None
        self.default_install_dir = None

        ctx.define_subparsers("main", desc)

        psr = ctx.get_parser('main.mods.build')
        psr.add_argument("mod_names", type=str,
                         help="List of modules that we should build")
        psr.add_argument("-d", "--dir", dest='mod_install_dir', type=str,
                         help="Destination where to install the blue prints")

        psr = ctx.get_parser('main.mods.install')
        psr.add_argument("ctx_names", type=str, nargs="?", default="default",
                         help="List of module contexts that we should deploy")

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 == 'mods':

            cmd1 = self.ctx.get_command(1)

            if cmd1 == 'build':
                bprints = self.get_param("mod_names").split(",")
                dest_dir = self.get_param("mod_install_dir", None)
                self.build_modules(bprints, dest_dir)
                return True

            if cmd1 == 'install':
                bpctx = self.get_param("ctx_names").split(",")
                proj = self.ctx.get_current_project()
                assert proj is not None, "Invalid current project for command bprint install"
                self.install_module_sets(proj, bpctx)
                return True

        return False

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.build_dir = self.get_path(self.ctx.get_root_dir(), "build")
            self.default_install_dir = self.get_path(self.ctx.get_root_dir(), "dist", "bin")
            self.collect_modules()
            bman = self.get_component('builder')
            self.builder = NVPBuilder(bman)
            self.builder.init_env()
            self.initialized = True

    def collect_modules(self):
        """Collect the available modules"""
        if self.modules is None:
            self.modules = self.config.get("modules", {})
            root_dir = self.ctx.get_root_dir()
            for _name, desc in self.modules.items():
                desc['url'] = desc['url'].replace("${NVP_ROOT_DIR}", root_dir)

        return self.modules

    def build_modules(self, mod_names, install_dir):
        """Build/install the list of modules"""

        self.initialize()
        modules = self.modules

        # Iterate on all the module names:
        for bp_name in mod_names:
            assert bp_name in modules, f"Cannot find module {bp_name}"
            self.build_module(bp_name, install_dir)

    def build_module(self, bp_name, install_dir):
        """Install a specific module"""

        if install_dir is None:
            install_dir = self.default_install_dir

        desc = self.modules[bp_name]

        # we should run a cmake command
        build_dir = self.get_path(self.build_dir, bp_name)
        self.make_folder(build_dir)

        src_dir = desc["url"]

        flags = []
        # check if we have dependencies:
        deps = desc.get("dependencies", {})

        bman = self.get_component('builder')
        tool = self.get_component('tools')

        for var_name, tgt in deps.items():
            # For now we just expect the target to be a library name:
            # or a tool name:
            parts = tgt.split(":")
            lib_name = parts[0]
            vtype = "root_dir" if len(parts) == 1 else parts[1]

            if vtype == "root_dir":
                if bman.has_library(lib_name):
                    var_val = bman.get_library_root_dir(lib_name)
                else:
                    var_val = tool.get_tool_root_dir(lib_name)

                var_val = var_val.replace("\\", "/")
            elif vtype == "version_major":
                desc = bman.get_library_desc(lib_name) or tool.get_tool_desc(lib_name)
                parts = desc['version'].split(".")
                var_val = parts[0]
            elif vtype == "version_minor":
                desc = bman.get_library_desc(lib_name) or tool.get_tool_desc(lib_name)
                parts = desc['version'].split(".")
                var_val = parts[1]

            flags.append(f"-D{var_name}={var_val}")

        self.builder.run_cmake(build_dir, install_dir, src_dir, flags)
        self.builder.run_ninja(build_dir)

    def install_module_sets(self, proj: NVPProject, bpctx):
        """Install a list of module contexts in a given project"""

        self.initialize()

        pcfg = proj.get_config()
        contexts = pcfg.get("module_sets", {})

        proot_dir = proj.get_root_dir()

        for ctx_name in bpctx:
            logger.info("Should install module set '%s' in %s", ctx_name, proj.get_name())
            mods = contexts[ctx_name]
            for mod_desc in mods:
                logger.info("Should install module %s", mod_desc['name'])
                mname = mod_desc['name']
                dest_dir = mod_desc['dir'].replace("${PROJECT_ROOT_DIR}", proot_dir)
                self.build_module(mname, dest_dir)