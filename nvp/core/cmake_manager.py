"""CMakeManager module"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return CMakeManager(ctx)


class CMakeManager(NVPComponent):
    """Project command manager class"""

    def __init__(self, ctx: NVPContext):
        """Cmake manager constructor"""
        NVPComponent.__init__(self, ctx)

        self.cmake_projects = None
        self.builder = None
        self.build_dir = None
        self.default_install_dir = None

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == 'build':
            bprints = self.get_param("mod_names").split(",")
            dest_dir = self.get_param("mod_install_dir", None)
            self.build_modules(bprints, dest_dir)
            return True

        if cmd == 'install':
            bpctx = self.get_param("ctx_names").split(",")
            proj = self.ctx.get_current_project()
            assert proj is not None, "Invalid current project for command cmake install"
            self.install_module_sets(proj, bpctx)
            return True

        if cmd == 'project.init':
            pname = self.get_param("cproj_name").split(",")
            proj = self.get_cmake_project(pname)
            assert proj is not None, f"Invalid Cmake project {pname}"
            self.init_cmake_project(proj)
            return True

        return False

    def get_cmake_project(self, pname):
        """Retrieve a project by name"""
        # Note: the projec must exist below:
        return self.cmake_projects[pname]

    def init_cmake_project(self, cproj):
        """Initialize the cmake project if not initialized yet"""
        logger.info("Should init cmake project here: %s", cproj)

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.build_dir = self.get_path(self.ctx.get_root_dir(), "build")
            self.default_install_dir = self.get_path(self.ctx.get_root_dir(), "dist", "bin")
            self.collect_cmake_projects()
            bman = self.get_component('builder')
            self.builder = NVPBuilder(bman)
            self.builder.init_env()
            self.initialized = True

    def collect_cmake_projects(self):
        """Collect the available modules"""
        if self.cmake_projects is None:
            self.cmake_projects = self.config.get("cmake_projects", {})
            root_dir = self.ctx.get_root_dir()
            for _name, desc in self.cmake_projects.items():
                desc['url'] = desc['url'].replace("${NVP_ROOT_DIR}", root_dir)

        return self.cmake_projects

    def build_modules(self, proj_names, install_dir):
        """Build/install the list of modules"""

        self.initialize()
        cprojects = self.cmake_projects

        # Iterate on all the module names:
        for cp_name in proj_names:
            assert cp_name in cprojects, f"Cannot find module {cp_name}"
            self.build_module(cp_name, install_dir)

    def build_module(self, cp_name, install_dir):
        """Install a specific module"""

        if install_dir is None:
            install_dir = self.default_install_dir

        desc = self.cmake_projects[cp_name]

        # we should run a cmake command
        build_dir = self.get_path(self.build_dir, cp_name)
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


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("cmake")

    psr = context.build_parser("build")
    psr.add_str("mod_names")("List of modules to build")
    psr.add_str("-d", "--dir", dest="mod_install_dir")("Install folder.")

    psr = context.build_parser("install")
    psr.add_str("ctx_names", nargs="?", default="default")("List of module context to install")

    psr = context.build_parser("project.init")
    psr.add_str("cproj_name")("Cmake project to init")

    comp.run()
