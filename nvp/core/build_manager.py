"""Module for build management system"""

import logging
import os
import sys
import time
from importlib import import_module

from nvp.nvp_compiler import NVPCompiler
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return BuildManager(ctx)


class BuildManager(NVPComponent):
    """NervProj builder class"""

    def __init__(self, ctx: NVPContext):
        """Build manager constructor"""
        NVPComponent.__init__(self, ctx)

        self.tools = None
        self.libs_dir = None
        self.libs_package_dir = None
        self.libs_build_dir = self.make_folder(ctx.get_root_dir(), "build", "libraries")

        # Setup the paths:
        self.compiler = None
        self.compilers = None
        self.builders = None

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.initialized = True
            self.select_compiler()
            self.tools = self.ctx.get_component("tools")

    def select_compiler(self, comp_type=None):
        """Find the available compilers on the current platform"""

        # Figure out what type of compiler should be used:
        if self.is_windows:
            supported_compilers = self.config.get("windows_supported_compilers", ["clang", "msvc"])
            comp_type = comp_type or self.config.get("windows_default_compiler_type", "msvc")
        if self.is_linux:
            supported_compilers = self.config.get("linux_supported_compilers", ["clang"])
            comp_type = comp_type or self.config.get("linux_default_compiler_type", "clang")

        self.compilers = []

        if self.is_windows:
            # Check if we have MSVC paths to use:

            msvc_setup_path = os.getenv("NVL_MSVC_SETUP")

            if msvc_setup_path is None:
                msvc_paths = self.config.get("msvc_install_paths", [])
                msvc_paths = [self.get_path(bdir, "VC/Auxiliary/Build/vcvarsall.bat") for bdir in msvc_paths]
                msvc_setup_path = self.ctx.select_first_valid_path(msvc_paths)

            assert msvc_setup_path is not None, "No MSVC compiler found."

            if msvc_setup_path is not None:
                compiler = NVPCompiler(self.ctx, {"type": "msvc", "setup_path": msvc_setup_path})
                self.compilers.append(compiler)

        if comp_type == "clang":
            # check if we have a library providing clang:
            flavors = [f"{self.platform}_{ctype}" for ctype in supported_compilers]

            base_lib_dir = self.get_path(self.ctx.get_root_dir(), "libraries")

            all_libs = self.config["libraries"]
            for lib in all_libs:
                if lib["name"] == "LLVM":
                    # Here we need to figure out if we already have that library built/installed
                    # for a given flavor
                    for flavor in flavors:
                        vers = self.get_package_version(lib)
                        comp_dir = self.get_path(base_lib_dir, flavor, f"{lib['name']}-{vers}")
                        if self.path_exists(comp_dir):
                            compiler = NVPCompiler(self.ctx, {"type": "clang", "root_dir": comp_dir})
                            self.compilers.append(compiler)

            # Check if we have tools providing compilers:
            all_tools = self.config[f"{self.platform}_tools"]
            tools_dir = self.get_component("tools").get_tools_dir()

            for tdesc in all_tools:
                if tdesc["name"] == "clang":
                    vers = self.get_package_version(tdesc)
                    compiler = NVPCompiler(
                        self.ctx, {"type": "clang", "root_dir": self.get_path(tools_dir, f"{tdesc['name']}-{vers}")}
                    )
                    self.compilers.append(compiler)

        assert len(self.compilers) > 0, "No compiler available"

        self.compilers.sort(key=lambda x: x.get_weight(), reverse=True)
        # select the first compiler of the current type:
        for comp in self.compilers:
            if comp.get_type() == comp_type:
                self.compiler = comp
                break

        assert self.compiler is not None, f"Cannot find compiler of type {comp_type}"
        logger.info("Selecting compiler %s (in %s)", self.compiler.get_name(), self.compiler.get_root_dir())

        self.setup_paths()

    def load_builders(self):
        """Load the builder functions"""
        self.builders = {}
        bld_path = self.get_path(self.ctx.get_root_dir(), "nvp", "builders")

        # Get all .py files in that folder:
        bld_files = self.get_all_files(bld_path, "\\.py$")
        logger.debug("Found builder files: %s", bld_files)

        # load those components:
        # sys.path.insert(0, bld_path)

        for cname in bld_files:
            bld_name = cname[:-3]
            mod_name = f"nvp.builders.{bld_name}"
            bld_module = import_module(mod_name)
            bld_module.register_builder(self)
            del sys.modules[mod_name]

        # sys.path.pop(0)

    def register_builder(self, bname, handler):
        """Register a builder function"""
        self.builders[bname] = handler

    def setup_paths(self):
        """Setup the paths that will be used during build or run process."""

        # Store the deps folder:
        base_dir = self.ctx.get_root_dir()

        self.libs_dir = self.make_folder(base_dir, "libraries", f"{self.platform}_{self.compiler.get_type()}")

        # Store the packages in the destination library folder:
        self.libs_package_dir = self.libs_dir

    def has_library(self, lib_name):
        """Check if a given library is available"""
        for ldesc in self.config["libraries"]:
            if ldesc["name"] == lib_name:
                return True
        return False

    def get_library_desc(self, lib_name):
        """Retrieve library desc if available"""
        for ldesc in self.config["libraries"]:
            if ldesc["name"] == lib_name:
                return ldesc
        return None

    def get_library_root_dir(self, lib_name, auto_setup=True):
        """Retrieve the root dir for a given library"""

        # Iterate on all the available libraries:
        for ldesc in self.config["libraries"]:
            dep_name = self.get_std_package_name(ldesc)

            # First we check if we have the dependency target folder already:

            if ldesc["name"] == lib_name or dep_name == lib_name:
                dep_dir = self.get_path(self.libs_dir, dep_name)

                if auto_setup and not self.dir_exists(dep_dir):
                    logger.info("Running automatic setup for %s", lib_name)
                    self.check_libraries([lib_name])

                # That folder should exist:
                assert self.dir_exists(dep_dir), f"Library folder {dep_dir} doesn't exist yet."
                return dep_dir

        return None

    def get_library_package_name(self, dep_name):
        """Retrieve the library pacakge name that should be used for a given library"""
        ext = ".7z" if self.is_windows else ".tar.xz"
        return f"{dep_name}-{self.platform}-{self.compiler.get_type()}{ext}"

    def check_libraries(
        self, dep_list, rebuild=False, preview=False, append=False, keep_build=False, use_existing_src=False
    ):
        """Build all the libraries for NervProj."""

        # Iterate on each dependency:
        logger.debug("Checking libraries:")
        alldeps = self.config["libraries"]

        # Ensure we use only lower case for dependency names:
        dep_list = [dname.lower() for dname in dep_list]

        doall = "all" in dep_list

        for dep in alldeps:

            # Check if we should process that dependency:
            if not doall and not dep["name"].lower() in dep_list:
                continue

            if preview:
                self.setup_build_context(dep, use_existing_src)
                continue

            dep_name = self.get_std_package_name(dep)

            # First we check if we have the dependency target folder already:
            dep_dir = self.get_path(self.libs_dir, dep_name)

            if rebuild:
                logger.info("Removing previous build for %s", dep_name)
                self.remove_folder(dep_dir)

                # Also remove the previously built package:
                self.remove_file(self.libs_package_dir, self.get_library_package_name(dep_name))

            if not os.path.exists(dep_dir) or append:
                # Here we need to deploy that dependency:
                self.deploy_dependency(dep, rebuild, append, keep_build, use_existing_src)
            else:
                logger.debug("- %s: OK", dep_name)

        logger.debug("All libraries OK.")

    def deploy_dependency(self, desc, rebuild=False, append=False, keep_build=False, use_existing_src=False):
        """Build a given dependency given its description dict and the target
        directory where it should be installed."""

        dep_name = self.get_std_package_name(desc)
        src_pkg_name = self.get_library_package_name(dep_name)

        # Here we should check if we already have a pre-built package for that dependency:
        src_pkg_path = self.get_path(self.libs_package_dir, src_pkg_name)

        # if the package is not already available locally, maybe we can retrieve it remotely:
        if not self.file_exists(src_pkg_path) and not rebuild and not append:
            pkg_urls = self.config.get("package_urls", [])
            pkg_urls = [base_url + "libraries/" + src_pkg_name for base_url in pkg_urls]

            pkg_url = self.ctx.select_first_valid_path(pkg_urls)
            if pkg_url is not None:
                self.tools.download_file(pkg_url, src_pkg_path)

        if self.file_exists(src_pkg_path) and not append:
            # We should simply extract that package into our target dir:
            self.tools.extract_package(src_pkg_path, self.libs_dir, target_dir=dep_name)
        else:
            # We really need to build the dependency from sources instead:
            lib_name = desc["name"]

            if self.builders is None:
                self.load_builders()

            # We should now have the builder for that library available:
            assert lib_name in self.builders, f"No builder available for library '{lib_name}'"

            # build_env = compiler.get_env()
            # logger.info("Compiler build env is: %s", self.pretty_print(build_env))

            # env = os.environ.copy()
            # logger.info("Current environment: %s", self.pretty_print(env))

            # Prepare the build context:
            build_dir, prefix, dep_name = self.setup_build_context(desc, use_existing_src)

            # Execute the builder function:
            start_time = time.time()
            builder = self.builders[lib_name]
            builder.build(build_dir, prefix, desc)
            elapsed = time.time() - start_time

            # Finally we should create the package from that installed dependency folder
            # so that we don't have to build it the next time:
            self.tools.create_package(prefix, self.libs_package_dir, src_pkg_name)

            if not keep_build:
                logger.info("Removing build folder %s", build_dir)
                self.remove_folder(build_dir)

            logger.info("Done building %s (build time: %.2f seconds)", dep_name, elapsed)

    def get_package_version(self, desc):
        """Retrieve the version to use for a given package"""
        sp_vers = f"{self.platform}_version"
        if sp_vers in desc:
            return desc[sp_vers]

        # Return default version number:
        return desc["version"]

    def get_std_package_name(self, desc):
        """Return a standard package naem from base name and version"""
        return f"{desc['name']}-{self.get_package_version(desc)}"

    def setup_build_context(self, desc, use_existing_src, base_build_dir=None):
        """Prepare the build folder for a given dependency package
        We then return the build_dir, dep_name and target install prefix"""

        # First we need to download the source package if missing:
        if base_build_dir is None:
            base_build_dir = self.libs_build_dir

        # get the filename from the url:
        url = desc.get(f"{self.platform}_url", desc.get("url", None))
        assert url is not None, f"Invalid source url for {desc['name']}"

        filename = os.path.basename(url)

        # Note that at this point the url may be a git path.
        # so filename will be "reponame.git" for instance
        src_pkg = self.get_path(base_build_dir, filename)

        from_git = url.startswith("git@") or url.startswith("hg@")
        # once the source file is downloaded we should extract it:
        # build_dir = src_pkg if from_git else self.remove_file_extension(src_pkg)
        tgt_dir = self.get_std_package_name(desc)
        # build_dir = src_pkg if from_git else self.remove_file_extension(src_pkg)
        build_dir = src_pkg if from_git else self.get_path(base_build_dir, tgt_dir)

        # remove the previous source content if any:
        if not use_existing_src and self.dir_exists(build_dir):
            logger.info("Removing previous source folder %s", build_dir)
            self.remove_folder(build_dir)

        if not self.dir_exists(build_dir):
            # download file if needed:
            if not self.path_exists(src_pkg):
                self.tools.download_file(url, src_pkg)

            # Now extract the source folder:
            if not from_git:
                # use the extracted folder name here if any:
                extracted_dir = desc.get("extracted_dir", None)
                self.tools.extract_package(src_pkg, base_build_dir, target_dir=tgt_dir, extracted_dir=extracted_dir)
        else:
            logger.info("Using existing source folder %s", build_dir)

        dep_name = self.get_std_package_name(desc)
        prefix = self.get_path(self.libs_dir, dep_name)

        return (build_dir, prefix, dep_name)

    def get_compiler(self, ctype=None):
        """Retrieve the current compiler to use"""
        assert self.compiler is not None, "Current compiler not configured yet."
        if ctype is None:
            return self.compiler

        for compiler in self.compilers:
            if compiler.get_type() == ctype:
                return compiler

        assert False, f"No compiler found with type {ctype}"

    def get_flavor(self):
        """Retrieve the current flavor"""
        return f"{self.platform}_{self.compiler.get_type()}"

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "libs":
            self.initialize()
            # logger.info("List of settings: %s", self.settings)
            dlist = self.get_param("lib_names").split(",")
            rebuild = self.get_param("rebuild")
            preview = self.get_param("preview")
            append = self.get_param("append")
            keep_build = self.get_param("keep_build", False)
            use_existing_src = self.get_param("use_existing_src", False)
            ctype = self.get_param("compiler_type")
            if ctype is not None:
                self.select_compiler(ctype)

            self.check_libraries(dlist, rebuild, preview, append, keep_build, use_existing_src)
            return True

        if cmd == "project":
            proj_name = self.get_param("proj_name")
            proj = self.ctx.get_project(proj_name)
            self.get_component("project").build_project(proj)
            return True

        return False


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    bcomp = context.get_component("builder")

    psr = context.build_parser("project")
    psr.add_str("proj_name")("Project name")
    # psr.add_str("-c", "--compiler", dest="compiler_type")("Compiler for the build")

    psr = context.build_parser("libs")
    psr.add_str("lib_names")("List of libraries to build")
    psr.add_str("-c", "--compiler", dest="compiler_type")("Compiler for the build")
    psr.add_flag("--rebuild", dest="rebuild")("Force rebuilding from sources")
    psr.add_flag("--preview", dest="preview")("Preview sources only")
    psr.add_flag("-k", "--keep-build", dest="keep_build")("Keep the build folder after build")
    psr.add_flag("-a", "--append", dest="append")("Keep the install folder if existing")
    psr.add_flag("-u", "--use-existing-src", dest="use_existing_src")("Use an existing source folder")

    bcomp.run()
