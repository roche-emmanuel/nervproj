"""Collection of admin utility functions"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = ProjectManager(ctx)
    ctx.register_component('project', comp)


class ProjectManager(NVPComponent):
    """Project command manager class"""

    def __init__(self, ctx: NVPContext):
        """Project commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        desc = {
            "proj": {
                "build": None,
            }
        }
        ctx.define_subparsers("main", desc)

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 != 'proj':
            return False

        cmd1 = self.ctx.get_command(1)

        if cmd1 == 'build':
            proj = self.ctx.get_current_project()
            if proj is None:
                logger.warning("No project to build.")

            self.build_project(proj)
            return True

        return False

    def write_cmake_dependencies(self, deps):
        """Write an array of CMake compatible input paths from a list of dependency names"""
        result = []
        builder = self.get_component("builder")

        for dep_name in deps:
            dep_dir = builder.get_library_root_dir(dep_name)
            assert dep_dir is not None, f"Library {dep_name} is not available."
            result.append(f"-D{dep_name.upper()}_DIR=\"{dep_dir}\"")

        return result

    def build_project(self, proj: NVPProject):
        """Build a given project."""

        assert proj is not None, "Invalid project."

        proj_dir = proj.get_root_dir()

        build_dir = self.get_path(proj_dir, "build", self.flavor)
        self.make_folder(build_dir)

        build_file = self.get_path(proj_dir, "build", f"build_{self.flavor}.bat")

        builder = self.get_component("builder")
        tools = self.get_component("tools")
        # generator = "NMake Makefiles JOM"

        generator = "Ninja"
        build_type = "Release"
        prefix = self.get_path(proj_dir, "dist", "bin", self.flavor)
        self.make_folder(prefix)

        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(f"call {builder.get_msvc_setup_path()} amd64\n")
            # Configure with cmake:
            cmd = [tools.get_cmake_path(),
                   f"-G \"{generator}\"",
                   f"-DCMAKE_BUILD_TYPE={build_type}",
                   f"-DCMAKE_INSTALL_PREFIX=\"{prefix}\"",
                   ]

            # Add the path of the dependencies for this project:
            deps = proj.get_dependencies()
            cmd += self.write_cmake_dependencies(deps)

            # Add the final project source path:
            cmd += [f"\"{proj_dir}\"\n"]

            bfile.write(" ".join(cmd))

            # Then run ninja:
            # bfile.write(f"{tools.get_ninja_path()}\n")

            # Then run ninja and install:
            bfile.write(f"{tools.get_ninja_path()} install\n")

        # Call the script:
        cmd = [build_file]
        logger.info("Building project %s...", proj.get_name(False))
        self.execute(cmd, cwd=build_dir)
