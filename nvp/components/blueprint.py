"""BlueprintManager module"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = BlueprintManager(ctx)
    ctx.register_component('blueprint', comp)


class BlueprintManager(NVPComponent):
    """Project command manager class"""

    def __init__(self, ctx: NVPContext):
        """Project commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        desc = {
            "bprint": {"build": None}
        }

        self.blueprints = None
        self.builder = None
        self.build_dir = None
        self.default_install_dir = None

        ctx.define_subparsers("main", desc)

        psr = ctx.get_parser('main.bprint.build')
        psr.add_argument("bp_names", type=str,
                         help="List of blueprints that we should build")
        psr.add_argument("-d", "--dir", dest='bp_install_dir', type=str,
                         help="Destination where to install the blue prints")

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 == 'bprint':

            cmd1 = self.ctx.get_command(1)

            if cmd1 == 'build':
                bprints = self.get_param("bp_names").split(",")
                dest_dir = self.get_param("bp_install_dir", None)
                self.install_blueprints(bprints, dest_dir)
                return True

        return False

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.build_dir = self.get_path(self.ctx.get_root_dir(), "build")
            self.default_install_dir = self.get_path(self.ctx.get_root_dir(), "dist", "bin")
            self.collect_blueprints()
            bman = self.get_component('builder')
            self.builder = NVPBuilder(bman)
            self.builder.init_env()
            self.initialized = True

    def collect_blueprints(self):
        """Collect the available blueprints"""
        if self.blueprints is None:
            self.blueprints = self.config.get("blueprints", {})
            root_dir = self.ctx.get_root_dir()
            for _name, desc in self.blueprints.items():
                desc['url'] = desc['url'].replace("${NVP_ROOT_DIR}", root_dir)

        return self.blueprints

    def install_blueprints(self, bp_names, install_dir):
        """Install the list of blueprints"""

        self.initialize()
        blueprints = self.blueprints

        # Iterate on all the blueprint names:
        for bp_name in bp_names:
            assert bp_name in blueprints, f"Cannot find blueprint {bp_name}"
            self.install_blueprint(bp_name, install_dir)

    def install_blueprint(self, bp_name, install_dir):
        """Install a specific blueprint"""

        if install_dir is None:
            install_dir = self.default_install_dir

        desc = self.blueprints[bp_name]

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
