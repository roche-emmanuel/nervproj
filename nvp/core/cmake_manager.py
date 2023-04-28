"""CMakeManager module"""
import logging
import math
import time

from nvp.nvp_builder import NVPBuilder
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject

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

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "build":
            bprints = self.get_param("proj_names").split(",")
            dest_dir = self.get_param("mod_install_dir", None)
            rebuild = self.get_param("rebuild")
            comp_type = self.get_param("compiler_type")
            bman = self.get_component("builder")
            bman.select_compiler(comp_type)

            self.build_projects(bprints, dest_dir, rebuild=rebuild)
            return True

        if cmd == "install":
            bpctx = self.get_param("ctx_names").split(",")
            proj = self.ctx.get_current_project()
            assert proj is not None, "Invalid current project for command cmake install"
            self.install_module_sets(proj, bpctx)
            return True

        if cmd == "setup":
            pname = self.get_param("cproj_name")
            proj = self.get_cmake_project(pname)
            self.check(proj is not None, "Invalid Cmake project %s", pname)
            self.setup_cmake_project(proj)
            gen_cmds = self.get_param("gen_commands")
            reconfig = self.get_param("reconfig")
            comp_type = self.get_param("compiler_type")
            bman = self.get_component("builder")
            bman.select_compiler(comp_type)

            if gen_cmds:
                # Also generate the compile_commands.json file:
                self.build_project(pname, None, gen_commands=True, rebuild=reconfig)
            return True

        if cmd == "add.header":
            pname = self.get_param("cproj_name")
            proj = self.get_cmake_project(pname)
            self.check(proj is not None, "Invalid Cmake project %s", pname)

            mod_name = self.get_param("mod_name")
            file_name = self.get_param("file_name")
            self.add_header_file(proj, mod_name, file_name)

            return True

        if cmd == "add.class":
            pname = self.get_param("cproj_name")
            proj = self.get_cmake_project(pname)
            self.check(proj is not None, "Invalid Cmake project %s", pname)

            mod_name = self.get_param("mod_name")
            file_name = self.get_param("file_name")
            ctype = self.get_param("class_type")
            force = self.get_param("force_write")

            self.add_class_files(proj, mod_name, file_name, ctype, rewrite=force)

            return True

        if cmd == "add.nervbind":

            mname = self.get_param("mod_name")

            self.add_nervbind(mname, self.get_cwd())

            return True

        return False

    def add_nervbind(self, mname, base_folder):
        """Add the initial files to generate lua bindings"""

        # logger.info("Should add nervbind for %s in %s", mname, base_folder)
        folder = self.get_path(base_folder, mname)
        self.make_folder(folder)
        self.make_folder(folder, "include")
        content = """#ifndef BIND_CONTEXT_
#define BIND_CONTEXT_

// Should put include files here.

#endif"""
        self.write_text_file(content, folder, "include", "bind_context.h")

        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")
        tpl_file = self.get_path(template_dir, "nervbind.lua.tpl")
        dst_file = self.get_path(folder, "nervbind.lua")
        hlocs = {"%TARGET_NAME%": mname, "%TARGET_NAME_LOWER%": mname.lower()}

        self.write_project_file(hlocs, dst_file, tpl_file)

    def add_header_file(self, cproj, mod_name, file_name):
        """Add a new header file in a the given module"""
        proj_dir = cproj["root_dir"]

        # Add .h to the end of the file if needed:
        if not file_name.endswith(".h"):
            file_name += ".h"

        mdesc = self.get_module_desc(cproj, mod_name)
        self.check(mdesc is not None, "invalid cmake project module %s", mod_name)

        mod_dir = mod_name
        if mdesc.get("type", "library") == "library":
            mod_dir = f"{cproj['prefix']}{mod_name}"

        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")

        dest_file = self.get_path(proj_dir, "modules", mod_dir, "src", file_name)
        bname = self.remove_file_extension(self.get_filename(file_name))

        tpl_file = self.get_path(template_dir, "header_file.h.tpl")

        hlocs = {"%PROJ_PREFIX_UPPER%": cproj["prefix"].upper(), "%HEADER_NAME_UPPER%": bname.upper()}

        self.write_project_file(hlocs, dest_file, tpl_file)

    def add_class_files(self, cproj, mod_name, class_name, ctype, rewrite):
        """Add a new class in a the given module"""
        proj_dir = cproj["root_dir"]
        prefix = cproj["prefix"]
        mdesc = self.get_module_desc(cproj, mod_name)
        self.check(mdesc is not None, "invalid cmake project module %s", mod_name)

        mod_dir = mod_name
        if mdesc.get("type", "library") == "library":
            mod_dir = f"{prefix}{mod_name}"

        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")

        dest_file = self.get_path(proj_dir, "modules", mod_dir, "src", f"{class_name}.h")

        if rewrite and self.file_exists(dest_file):
            self.remove_file(dest_file)

        parent_dir = self.get_parent_folder(dest_file)
        self.make_folder(parent_dir)

        bname = self.remove_file_extension(self.get_filename(class_name))

        tpl_file = self.get_path(template_dir, "class_header.h.tpl")

        if ctype is None:
            ctype = cproj.get("default_class_template", "default")

        if ctype == "default":
            content_tpl = self.read_text_file(template_dir, "default_class.tpl")
        else:
            ctpl_file = cproj["content_templates"][ctype]
            ctpl_file = self.get_path(proj_dir, "cmake", "templates", ctpl_file)
            content_tpl = self.read_text_file(ctpl_file)

        # We just replace the content part in our global template:
        header_tpl = self.read_text_file(tpl_file)
        header_tpl = header_tpl.replace("%CLASS_CONTENT%", content_tpl)

        hlocs = {
            "%PROJ_PREFIX_UPPER%": prefix.upper(),
            "%CLASS_NAME_UPPER%": bname.upper(),
            "%BEGIN_NAMESPACE%": f"namespace {prefix} " + "{",
            "%END_NAMESPACE%": "}",
            "%NAMESPACE%": prefix,
            "%CLASS_NAME%": bname,
            "%CLASS_EXPORT%": f"{mod_dir.upper()}_EXPORT",
            "%CLASS_INCLUDE%": f"{class_name}.h",
        }

        self.write_project_file_content(hlocs, dest_file, header_tpl)

        dest_file = self.get_path(proj_dir, "modules", mod_dir, "src", f"{class_name}.cpp")
        if rewrite and self.file_exists(dest_file):
            self.remove_file(dest_file)

        tpl_file = self.get_path(template_dir, "class_impl.cpp.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        # generate the compile commands:
        self.build_project(cproj["name"].lower(), None, gen_commands=True)

    def get_module_desc(self, cproj, mod_name):
        """Retrieve a module desc by name"""
        mods = cproj["modules"]
        for desc in mods:
            if desc["name"] == mod_name:
                return desc

        return None

    def get_cmake_project(self, pname):
        """Retrieve a project by name"""
        # Note: the projec must exist below:
        return self.cmake_projects[pname]

    def setup_vscode_settings(self, proj):
        """Setup the vscode settings in a given NVP project for C++ compilation support"""
        settings_file = self.get_path(proj.get_root_dir(), ".vscode", "settings.json")

        logger.info("Settings up vscode settings in %s", settings_file)

        # First we must ensure that the LLVm library is deployed:
        bman = self.get_component("builder")

        # Ensure LLVM is installed:
        logger.info("Checking LLVM library...")
        bman.check_libraries(["llvm"])

        llvm_dir = bman.get_library_root_dir("LLVM")
        logger.info("Using LLVM root dir: %s", llvm_dir)

        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")
        dest_file = self.get_path(proj.get_root_dir(), ".clang-format")
        tpl_file = self.get_path(template_dir, "clang_format.tpl")
        self.write_project_file({}, dest_file, tpl_file)

        dest_file = self.get_path(proj.get_root_dir(), ".clang-tidy")
        tpl_file = self.get_path(template_dir, "clang_tidy.tpl")
        self.write_project_file({}, dest_file, tpl_file)

        dest_file = self.get_path(proj.get_root_dir(), ".clangd")
        tpl_file = self.get_path(template_dir, "clangd.tpl")
        self.write_project_file({}, dest_file, tpl_file)

        # Try to load the existing config if any:
        settings = {}
        ref_settings = None
        if self.file_exists(settings_file):
            settings = self.read_json(settings_file)
            ref_settings = self.read_json(settings_file)

        # Add our settings:
        ext = ".exe" if self.is_windows else ""

        settings["editor.formatOnSave"] = True
        clang_format_path = self.get_path(llvm_dir, "bin", f"clang-format{ext}")
        clang_format_path = clang_format_path.replace("\\", "/")
        clang_tidy_path = self.get_path(llvm_dir, "bin", f"clang-tidy{ext}")
        clang_tidy_path = clang_tidy_path.replace("\\", "/")
        settings["C_Cpp.clang_format_path"] = clang_format_path
        settings["C_Cpp.clang_format_style"] = "file"
        # settings["C_Cpp.codeAnalysis.clangTidy.path"] = clang_tidy_path
        # settings["C_Cpp.codeAnalysis.clangTidy.enabled"] = True
        # settings["C_Cpp.codeAnalysis.runAutomatically"] = True
        settings["cmake.buildDirectory"] = "${workspaceFolder}/.cache/cmake"

        # "clangd.arguments": ["-log=verbose"]

        if ref_settings is None or settings != ref_settings:
            logger.info("Wrtting updated vscode settings in %s", settings_file)
            self.write_json(settings, settings_file)
        else:
            logger.info("No change in %s", settings_file)

    def setup_cmake_project(self, cproj):
        """Initialize the cmake project if not initialized yet"""

        # First we should setting the vscode settings in the parent nvp project:
        if "nvp_project" in cproj:
            proj_name = cproj["nvp_project"]
            # logger.info("CmakeManager: Setting up NVP project %s", proj_name)
            proj = self.ctx.get_project(proj_name)
            self.setup_vscode_settings(proj)

        # Create the main cmakelists file if needed:
        proj_dir = cproj["root_dir"]
        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")

        proj_name = cproj["name"]
        logger.info("Setting up %s...", proj_name)

        hlocs = {
            "%PROJ_NAME%": proj_name,
            "%PROJ_VERSION%": cproj["version"],
            "%PROJ_PREFIX_UPPER%": cproj["prefix"].upper(),
        }

        dest_file = self.get_path(proj_dir, "CMakeLists.txt")
        tpl_file = self.get_path(template_dir, "main_cmakelists.txt.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        # Create the cmake folder:
        cmake_dir = self.get_path(proj_dir, "cmake")
        self.make_folder(cmake_dir)

        dest_file = self.get_path(proj_dir, "cmake", "Macros.cmake")
        tpl_file = self.get_path(template_dir, "cmake_macros.cmake.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        # Create the source/tests folder:
        src_dir = self.get_path(proj_dir, "modules")
        self.make_folder(src_dir)

        dest_file = self.get_path(src_dir, "CMakeLists.txt")
        if not self.file_exists(dest_file):
            logger.info("Writing file %s", dest_file)
            content = f"# CMake modules for {proj_name}\n"
            self.write_text_file(content, dest_file)

        # Create the test folder:
        test_dir = self.get_path(proj_dir, "tests")
        self.make_folder(test_dir)

        dest_file = self.get_path(test_dir, "CMakeLists.txt")
        if not self.file_exists(dest_file):
            logger.info("Writing file %s", dest_file)
            content = f"# Cmake tests for {proj_name} modules\n"
            self.write_text_file(content, dest_file)

        # Add the libraries/executables if any:
        mods = cproj.get("modules", [])
        for desc in mods:
            mtype = desc.get("type", "library")
            if mtype == "library":
                self.add_library(cproj, desc)
            elif mtype == "executable":
                self.add_executable(cproj, desc)
            else:
                self.throw("Unsupported cmake module type: %s", mtype)

    def write_project_file_content(self, hlocs, dest_file, content):
        """Write some string content in destination file"""
        if not self.file_exists(dest_file):
            logger.info("Writing file %s", dest_file)
            content = self.fill_placeholders(content, hlocs)
            self.write_text_file(content, dest_file)

    def write_project_file(self, hlocs, dest_file, tpl_file):
        """Write a module file from a given template"""
        content = self.read_text_file(tpl_file)
        self.write_project_file_content(hlocs, dest_file, content)

    def append_unique_line(self, dest_file, new_line):
        """Uniquely append a newline at the end of a given file if not present already"""
        content = self.read_text_file(dest_file)
        lines = content.splitlines()

        for line in lines:
            if line.strip() == new_line:
                return

        logger.info("Appending '%s' to %s", new_line, dest_file)
        lines.append(new_line)
        self.write_text_file("\n".join(lines), dest_file)

    def add_library(self, cproj, desc):
        """Add a new library to the given project"""
        # logger.info("Adding library %s to project %s", desc['name'], cproj['name'])

        proj_dir = cproj["root_dir"]
        prefix = cproj["prefix"]

        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")

        # Create the source library folder if needed:
        lib_name = desc["name"]
        lib_dir = self.get_path(proj_dir, "modules", f"{prefix}{lib_name}")
        self.make_folder(lib_dir)

        hlocs = {
            "%PROJ_PREFIX_UPPER%": prefix.upper(),
            "%PROJ_PREFIX%": prefix,
            "%TARGET_NAME%": f"{prefix}{lib_name}",
            "%LIB_NAME_LOWER%": lib_name.lower(),
            "%LIB_NAME_UPPER%": lib_name.upper(),
        }

        # Should add the module to the main CmakeLists.txt file:
        cmake_file = self.get_path(proj_dir, "modules", "CMakeLists.txt")
        new_line = f"add_subdirectory({prefix}{lib_name})"
        self.append_unique_line(cmake_file, new_line)

        # Add the Cmake file in the lib dir:
        dest_file = self.get_path(lib_dir, "CMakeLists.txt")
        tpl_file = self.get_path(template_dir, "library_cmakelists.txt.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        # In this library directory we should have the src/static/shared folders.
        self.make_folder(self.get_path(lib_dir, "src"))

        # Write the module default files:
        dest_file = self.get_path(lib_dir, "src", f"{lib_name.lower()}_common.cpp")
        tpl_file = self.get_path(template_dir, "module_common.cpp.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)
        dest_file = self.get_path(lib_dir, "src", f"{lib_name.lower()}_common.h")
        tpl_file = self.get_path(template_dir, "module_common.h.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)
        dest_file = self.get_path(lib_dir, "src", f"{lib_name.lower()}_precomp.h")
        tpl_file = self.get_path(template_dir, "module_precomp.h.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)
        dest_file = self.get_path(lib_dir, "src", f"{lib_name.lower()}_exports.h")
        tpl_file = self.get_path(template_dir, "module_exports.h.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        self.make_folder(self.get_path(lib_dir, "static"))

        # Not needed:
        # dest_file = self.get_path(lib_dir, "static", f"{lib_name.lower()}_precomp.cpp")
        # tpl_file = self.get_path(template_dir, "module_precomp.cpp.tpl")
        # self.write_project_file(hlocs, dest_file, tpl_file)

        dest_file = self.get_path(lib_dir, "static", "CMakeLists.txt")
        tpl_file = self.get_path(template_dir, "module_static_cmakelists.txt.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        self.make_folder(self.get_path(lib_dir, "shared"))

        # Not needed:
        # dest_file = self.get_path(lib_dir, "shared", f"{lib_name.lower()}_precomp.cpp")
        # tpl_file = self.get_path(template_dir, "module_precomp.cpp.tpl")
        # self.write_project_file(hlocs, dest_file, tpl_file)

        dest_file = self.get_path(lib_dir, "shared", "CMakeLists.txt")
        tpl_file = self.get_path(template_dir, "module_shared_cmakelists.txt.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

    def add_executable(self, cproj, desc):
        """Add an executable to the given project"""

        proj_dir = cproj["root_dir"]
        prefix = cproj["prefix"]

        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")

        # Create the source library folder if needed:
        app_name = desc["name"]
        app_dir = self.get_path(proj_dir, "modules", app_name)
        self.make_folder(app_dir)

        hlocs = {"%PROJ_PREFIX_UPPER%": prefix.upper(), "%PROJ_PREFIX%": prefix, "%TARGET_NAME%": app_name}

        # Should add the module to the main CmakeLists.txt file:
        cmake_file = self.get_path(proj_dir, "modules", "CMakeLists.txt")
        new_line = f"add_subdirectory({app_name})"
        self.append_unique_line(cmake_file, new_line)

        dest_file = self.get_path(app_dir, "CMakeLists.txt")
        tpl_file = self.get_path(template_dir, "executable_cmakelists.txt.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

        # In this library directory we should have the src/static/shared folders.
        self.make_folder(self.get_path(app_dir, "src"))

        # Write the module default files:
        dest_file = self.get_path(app_dir, "src", "main.cpp")
        tpl_file = self.get_path(template_dir, "executable_main.cpp.tpl")
        self.write_project_file(hlocs, dest_file, tpl_file)

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.build_dir = self.get_path(self.ctx.get_root_dir(), "build")
            self.collect_cmake_projects()
            self.initialized = True

    def get_builder(self):
        """Retrieve the builder associated to this component"""
        if self.builder is None:
            bman = self.get_component("builder")
            self.builder = NVPBuilder(bman)
            self.builder.init_env()

        return self.builder

    def collect_cmake_projects(self):
        """Collect the available modules"""
        if self.cmake_projects is None:
            self.cmake_projects = {}
            root_dir = self.ctx.get_root_dir().replace("\\", "/")
            hlocs = {"${NVP_ROOT_DIR}": root_dir}

            cprojs = self.config.get("cmake_projects", [])
            for desc in cprojs:
                pname = desc["name"].lower()
                desc["root_dir"] = self.fill_placeholders(desc["root_dir"], hlocs)
                self.check(pname not in self.cmake_projects, "Cmake project %s already registered.", pname)
                self.cmake_projects[pname] = desc

            # Alos iterate on the sub projects to find the cmake projects:
            for proj in self.ctx.get_projects():
                cprojs = proj.get_config().get("cmake_projects", [])
                root_dir = proj.get_root_dir()
                # We may not have a root dir locally for that project?
                if root_dir is None:
                    logger.debug("No root dir available for %s", proj.get_name(False))
                    continue

                proj_dir = root_dir.replace("\\", "/")
                hlocs["${PROJECT_ROOT_DIR}"] = proj_dir
                for desc in cprojs:
                    pname = desc["name"].lower()
                    desc["root_dir"] = self.fill_placeholders(desc["root_dir"], hlocs)
                    desc["install_dir"] = self.fill_placeholders(desc["install_dir"], hlocs)

                    # Add the project name:
                    desc["nvp_project"] = proj.get_name(False)

                    self.check(pname not in self.cmake_projects, "Cmake project %s already registered.", pname)
                    self.cmake_projects[pname] = desc

        return self.cmake_projects

    def build_projects(self, proj_names, install_dir, rebuild=False):
        """Build/install the list of projects"""

        self.initialize()
        cprojects = self.cmake_projects

        # Iterate on all the module names:
        for proj_name in proj_names:
            assert proj_name in cprojects, f"Cannot find module {proj_name}"
            self.build_project(proj_name, install_dir, rebuild)

    def install_dep_modules(self, proj_name, install_dir, platform):
        """Install all the dependencies for a given project"""
        desc = self.cmake_projects[proj_name]

        if install_dir is None:
            install_dir = desc["install_dir"]

        bman = self.get_component("builder")
        tool = self.get_component("tools")

        key = f"{platform}_dep_modules"
        mods = desc.get(key, {})

        for lib_name, file_map in mods.items():
            # logger.info("Should install modules for %s: %s", lib_name, file_map)
            # get the root path of that dependency:
            if bman.has_library(lib_name):
                root_dir = bman.get_library_root_dir(lib_name)
            else:
                root_dir = tool.get_tool_root_dir(lib_name)

            # Iterate on each file to check if it's already installed or not:
            for src_file, dst_locs in file_map.items():
                # dst_locs could be a simple string or a list, we convert this to a list anyway:
                if isinstance(dst_locs, str):
                    dst_locs = [dst_locs]

                # We should iterate on each target location:
                for dst_loc in dst_locs:
                    # if the dst_loc ends with a "/" character, it means we want to use the source file name:
                    if dst_loc[-1] == "/":
                        fname = self.get_filename(src_file)
                        dst_file = self.get_path(dst_loc[:-1], fname)
                    else:
                        dst_file = dst_loc

                    src_path = self.get_path(root_dir, src_file)
                    dst_path = self.get_path(install_dir, dst_file)
                    copy_needed = False

                    if self.file_exists(dst_path):
                        # Check if the hash will match:
                        hash1 = self.compute_file_hash(src_path)
                        hash2 = self.compute_file_hash(dst_path)
                        if hash1 != hash2:
                            logger.info("Updating dep module %s...", dst_file)
                            self.remove_file(dst_path)
                            copy_needed = True
                    else:
                        # The destination file doesn't exist yet, we simply install it:
                        logger.info("Installing dep module %s...", dst_file)
                        copy_needed = True

                    if copy_needed:
                        # Check that the source file exists:
                        self.check(self.file_exists(src_path), "Invalid source file: %s", src_path)
                        folder = self.get_parent_folder(dst_path)
                        self.make_folder(folder)
                        self.copy_file(src_path, dst_path)

    def build_project(self, proj_name, install_dir, rebuild=False, gen_commands=False):
        """Build/install a specific project"""

        desc = self.cmake_projects[proj_name]

        if install_dir is None:
            install_dir = desc["install_dir"]

        bman = self.get_component("builder")
        ctype = bman.get_compiler().get_type()

        build_type = self.get_param("build_type", "Release")
        logger.info("Cmake build type: %s", build_type)

        # we should run a cmake command
        # For the build dir we should also append the compiler type:
        build_dir = self.get_path(self.build_dir, f"{proj_name}_{ctype}_{build_type.lower()}")

        if rebuild and self.dir_exists(build_dir):
            logger.info("Removing build folder %s", build_dir)
            self.remove_folder(build_dir, recursive=True)

        self.make_folder(build_dir)

        src_dir = desc["root_dir"]

        flags = []
        # check if we have dependencies:
        deps = desc.get("dependencies", {})

        tool = self.get_component("tools")

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
                parts = desc["version"].split(".")
                var_val = parts[0]
            elif vtype == "version_minor":
                desc = bman.get_library_desc(lib_name) or tool.get_tool_desc(lib_name)
                parts = desc["version"].split(".")
                var_val = parts[1]

            flags.append(f"-D{var_name}={var_val}")

        # Request generation of compile commands:
        flags.append("-DCMAKE_EXPORT_COMPILE_COMMANDS=1")

        if gen_commands and not bman.get_compiler().is_clang():
            # Ensure we select the clang compiler:
            bman.select_compiler("clang")

        # Write the build outputs to a build logfile:
        build_file = self.get_path(src_dir, f"{proj_name}_{ctype}_build.log")
        outfile = None if gen_commands else open(build_file, "w", encoding="utf-8", newline="")

        builder = self.get_builder()
        builder.run_cmake(build_dir, install_dir, src_dir, flags, outfile=outfile, build_type=build_type)

        if bman.get_compiler().is_clang():
            # Copy the compile_commands.json file:
            comp_file = self.get_path(build_dir, "compile_commands.json")
            self.check(self.file_exists(comp_file), "No file %s", comp_file)
            dst_file = self.get_path(src_dir, "compile_commands.json")
            self.rename_file(comp_file, dst_file)

        if gen_commands:
            # Don't actually run the build
            return

        nthreads = self.get_param("num_threads", None)
        flags = None
        if nthreads is not None:
            logger.info("Building with %d threads.", nthreads)
            flags = ["-j", str(nthreads)]
        start_tick = time.time()
        builder.run_ninja(build_dir, outfile=outfile, flags=flags)
        outfile.close()

        # Install the dependency modules:
        platform = self.platform
        if bman.get_compiler().is_emcc():
            platform = "emscripten"
        self.install_dep_modules(proj_name, install_dir, platform)

        elapsed = time.time() - start_tick
        mins = math.floor(elapsed / 60)
        elapsed = elapsed - mins * 60.0
        if mins > 0:
            logger.info("Build completed in %d mins %.3f secs", mins, elapsed)
        else:
            logger.info("Build completed in %.3f secs", elapsed)

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
                logger.info("Should install module %s", mod_desc["name"])
                mname = mod_desc["name"]
                dest_dir = mod_desc["dir"].replace("${PROJECT_ROOT_DIR}", proot_dir)
                self.build_project(mname, dest_dir)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("cmake")

    psr = context.build_parser("build")
    psr.add_str("proj_names")("List of modules to build")
    psr.add_str("-d", "--dir", dest="mod_install_dir")("Install folder")
    psr.add_flag("-r", "--rebuild", dest="rebuild")("Force rebuilding completely")
    psr.add_str("-t", "--build-type", dest="build_type", default="Release")("Specify the cmake build type")
    psr.add_str("-c", "--compiler", dest="compiler_type", default="clang")("Select the compiler")
    psr.add_int("-j", "--num-threads", dest="num_threads")("Specify the number of threads to use during build.")

    psr = context.build_parser("install")
    psr.add_str("ctx_names", nargs="?", default="default")("List of module context to install")

    psr = context.build_parser("setup")
    psr.add_str("cproj_name")("Cmake project to init")
    psr.add_flag("-g", dest="gen_commands")("Generate the compile_commands.json file")
    psr.add_flag("-r", "--reconfig", dest="reconfig")("Force reconfiguring completely")
    psr.add_str("-c", "--compiler", dest="compiler_type", default="clang")("Select the compiler")

    psr = context.build_parser("add.header")
    psr.add_str("cproj_name")("Cmake project")
    psr.add_str("mod_name")("Module name")
    psr.add_str("file_name")("Header file name")

    psr = context.build_parser("add.class")
    psr.add_str("cproj_name")("Cmake project")
    psr.add_str("mod_name")("Module name")
    psr.add_str("file_name")("class file name")
    psr.add_str("-t", dest="class_type")("Type of the class to create.")
    psr.add_flag("-f", dest="force_write")("Force rewriting the class files")

    psr = context.build_parser("add.nervbind")
    psr.add_str("mod_name")("Module name")

    comp.run()
