"""Module for build management system"""

import os
import sys
import logging
from nvp.nvp_compiler import NVPCompiler

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = BuildManager(ctx)
    ctx.register_component('builder', comp)


class BuildManager(NVPComponent):
    """NervProj builder class"""

    def __init__(self, ctx: NVPContext):
        """Build manager constructor"""
        NVPComponent.__init__(self, ctx)

        self.tools = None

        desc = {
            "build": {"libs": None},
        }
        ctx.define_subparsers("main", desc)
        psr = ctx.get_parser('main.build.libs')
        psr.add_argument("lib_names", type=str, nargs='?', default="all",
                         help="List of library names that we should build")
        psr.add_argument("--rebuild", dest='rebuild', action='store_true',
                         help="Force rebuilding from sources")

        psr = ctx.get_parser('main.build')

        # Setup the paths:
        self.setup_paths()
        self.compilers = []

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.initialized = True
            self.load_compilers()
            self.tools = self.ctx.get_component('tools')

    def load_compilers(self):
        """Find the available compilers on the current platform"""
        if self.is_windows:
            # Check if we have MSVC paths to use:

            msvc_setup_path = os.getenv('NVL_MSVC_SETUP')

            if msvc_setup_path is None:
                msvc_paths = self.config.get('msvc_install_paths', [])
                msvc_paths = [self.get_path(bdir, "VC/Auxiliary/Build/vcvarsall.bat")
                              for bdir in msvc_paths]
                msvc_setup_path = self.ctx.select_first_valid_path(msvc_paths)

            if msvc_setup_path is not None:
                comp = NVPCompiler({"type": "msvc", "setup_path": msvc_setup_path})
                self.compilers.append(comp)

        # check if we have a library providing clang:
        all_libs = self.config['libraries']
        for lib in all_libs:
            if lib['name'] == 'LLVM':
                comp = NVPCompiler({'type': 'clang', "root_dir": self.get_path(
                    self.libs_dir, f"{lib['name']}-{lib['version']}")})
                self.compilers.append(comp)

        # Check if we have tools providing compilers:
        all_tools = self.config[f"{sys.platform}_tools"]
        tools_dir = self.get_component('tools').get_tools_dir()

        for tdesc in all_tools:
            if tdesc['name'] == "clang":
                comp = NVPCompiler({'type': 'clang', "root_dir": self.get_path(
                    tools_dir, f"{tdesc['name']}-{tdesc['version']}")})
                self.compilers.append(comp)

        # Sort the compilers:
        self.sort_compilers()

    def sort_compilers(self):
        """Sort the available compilers based on weight and user selected type."""
        selected_type = self.settings.get("compiler_type", None)
        assert len(self.compilers) > 0, "No compiler available"

        self.compilers.sort(key=lambda x: x.get_weight(selected_type), reverse=True)

    def setup_paths(self):
        """Setup the paths that will be used during build or run process."""

        # Store the deps folder:
        base_dir = self.ctx.get_root_dir()
        self.libs_dir = self.make_folder(base_dir, "libraries", self.flavor)
        self.libs_build_dir = self.make_folder(base_dir, "libraries", "build")
        self.libs_package_dir = self.make_folder(base_dir, "libraries", self.flavor)

    def get_library_root_dir(self, lib_name):
        """Retrieve the root dir for a given library"""

        # Iterate on all the available libraries:
        for ldesc in self.config['libraries']:
            dep_name = self.get_std_package_name(ldesc)

            # First we check if we have the dependency target folder already:

            if ldesc['name'] == lib_name or dep_name == lib_name:
                dep_dir = self.get_path(self.libs_dir, dep_name)

                # That folder should exist:
                assert self.dir_exists(dep_dir), f"Library folder {dep_dir} doesn't exist yet."
                return dep_dir

        return None

    def check_libraries(self, dep_list):
        """Build all the libraries for NervProj."""

        # Iterate on each dependency:
        logger.debug("Checking libraries:")
        alldeps = self.config['libraries']

        doall = "all" in dep_list
        rebuild = self.settings['rebuild']

        for dep in alldeps:

            # Check if we should process that dependency:
            if not doall and not dep['name'].lower() in dep_list:
                continue

            dep_name = self.get_std_package_name(dep)

            # First we check if we have the dependency target folder already:
            dep_dir = self.get_path(self.libs_dir, dep_name)

            if rebuild:
                logger.debug("Removing previous build for %s", dep_name)
                self.remove_folder(dep_dir)

                # Also remove the previously built package:
                self.remove_file(self.libs_package_dir, f"{dep_name}-{self.flavor}.7z")

            if not os.path.exists(dep_dir):
                # Here we need to deploy that dependency:
                self.deploy_dependency(dep)
            else:
                logger.debug("- %s: OK", dep_name)

        logger.info("All libraries OK.")

    def deploy_dependency(self, desc):
        """Build a given dependency given its description dict and the target
        directory where it should be installed."""

        dep_name = self.get_std_package_name(desc)
        src_pkg_name = f"{dep_name}-{self.flavor}.7z"

        # Here we should check if we already have a pre-built package for that dependency:
        src_pkg_path = self.get_path(self.libs_package_dir, src_pkg_name)

        rebuild = self.settings['rebuild']

        # if the package is not already available locally, maybe we can retrieve it remotely:
        if not self.file_exists(src_pkg_path) and not rebuild:
            pkg_urls = self.config.get("package_urls", [])
            pkg_urls = [base_url+'libraries/'+src_pkg_name for base_url in pkg_urls]

            pkg_url = self.ctx.select_first_valid_path(pkg_urls)
            if pkg_url is not None:
                self.tools.download_file(pkg_url, src_pkg_path)

        if self.file_exists(src_pkg_path):
            # We should simply extract that package into our target dir:
            self.tools.extract_package(src_pkg_path, self.libs_dir, target_dir=dep_name)
        else:
            # We really need to build the dependency from sources instead:

            # Prepare the build context:
            build_dir, prefix, dep_name = self.setup_dependency_build_context(desc)

            # Find the build method that should be used for that dependency
            # and execute it:
            fname = f"_build_{desc['name']}_{self.flavor}"
            builder = self.get_method(fname.lower())
            builder(build_dir, prefix, desc)

            # Finally we should create the package from that installed dependency folder
            # so that we don't have to build it the next time:
            self.create_package(prefix, self.libs_package_dir, f"{dep_name}-{self.flavor}.7z")

            logger.info("Removing build folder %s", build_dir)
            self.remove_folder(build_dir)

            logger.info("Done building %s", dep_name)

    def get_std_package_name(self, desc):
        """Return a standard package naem from base name and version"""
        return f"{desc['name']}-{desc['version']}"

    def create_package(self, src_path, dest_folder, package_name):
        """Create an archive package given a source folder, destination folder
        and name for the zip file to create"""
        # 7z a -t7z -m0=lzma2 -mx=9 -aoa -mfb=64 -md=32m -ms=on -d=1024m -r

        # Note: we only create the package if the source folder exits:
        if not self.path_exists(src_path):
            logger.warning("Cannot create package: invalid source path: %s", src_path)
            return False

        cmd = [self.tools.get_unzip_path(), "a", "-t7z", self.get_path(dest_folder, package_name), src_path,
               "-m0=lzma2", "-mx=9", "-aoa", "-mfb=64",
               "-ms=on", "-mmt=2", "-r"]
        # "-md=32m",
        self.execute(cmd, self.settings['verbose'])
        logger.debug("Done generating package %s", package_name)
        return True

    def setup_dependency_build_context(self, desc):
        """Prepare the build folder for a given dependency package
        We then return the build_dir, dep_name and target install prefix"""

        # First we need to download the source package if missing:
        base_build_dir = self.libs_build_dir

        # get the filename from the url:
        url = desc.get(f"{self.platform}_url", desc.get('url', None))
        assert url is not None, f"Invalid source url for {desc['name']}"

        filename = os.path.basename(url)

        # Note that at this point the url may be a git path.
        # so filename will be "reponame.git" for instance
        src_pkg = self.get_path(base_build_dir, filename)

        from_git = url.startswith("git@")
        # once the source file is downloaded we should extract it:
        # build_dir = src_pkg if from_git else self.remove_file_extension(src_pkg)
        tgt_dir = self.get_std_package_name(desc)
        # build_dir = src_pkg if from_git else self.remove_file_extension(src_pkg)
        build_dir = src_pkg if from_git else self.get_path(base_build_dir, tgt_dir)

        # remove the previous source content if any:
        logger.info("Removing previous source folder %s", build_dir)
        self.remove_folder(build_dir)

        # download file if needed:
        if not self.path_exists(src_pkg):
            self.tools.download_file(url, src_pkg)

        # Now extract the source folder:
        if not from_git:
            # use the extracted folder name here if any:
            extracted_dir = desc.get("extracted_dir", None)
            self.tools.extract_package(src_pkg, base_build_dir, target_dir=tgt_dir, extracted_dir=extracted_dir)

        dep_name = self.get_std_package_name(desc)
        prefix = self.get_path(self.libs_dir, dep_name)

        return (build_dir, prefix, dep_name)

    def get_current_compiler(self):
        """Retrieve the current compiler to use"""
        return self.compilers[0]

    #############################################################################################
    # Builder functions:
    #############################################################################################

    def _build_llvm_msvc64(self, build_dir, prefix, _desc):
        """Build method for LLVM with msvc64 compiler."""

        compiler = self.get_current_compiler()

        # Create a sub build folder:
        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        tools = self.get_component('tools')
        python_dir = tools.get_tool_dir('python')

        # We write the temp.bat file:
        build_file = build_dir+"/build.bat"
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(compiler.get_init_script())
            # Add python to the path:
            bfile.write(f"set PATH={python_dir};%PATH%\n")
            # bfile.write(f"{self.tools.get_cmake_path()} -G \"NMake Makefiles\" -DCMAKE_BUILD_TYPE=Release ")
            bfile.write(f"{self.tools.get_cmake_path()} -G \"Ninja\" -DCMAKE_BUILD_TYPE=Release ")
            bfile.write(f"-DCMAKE_INSTALL_PREFIX=\"{prefix}\" -DLLVM_TARGETS_TO_BUILD=X86 ")
            # not including cross-project-tests
            bfile.write("-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libc;libclc;lld;lldb;openmp;polly;pstl ")
            bfile.write("-DLLVM_ENABLE_EH=ON -DLLVM_ENABLE_RTTI=ON ")
            bfile.write("..\\llvm\n")
            bfile.write(f"{tools.get_ninja_path()}\n")
            bfile.write(f"{tools.get_ninja_path()} install\n")
            # bfile.write("nmake\n")
            # bfile.write("nmake install\n")

        # other possible options:
        # -DLLVM_BUILD_TOOLS=ON -DLLVM_INCLUDE_TOOLS=ON
        # -DLLVM_BUILD_EXAMPLES=ON   -DLLVM_ENABLE_IDE=OFF  ..\llvm

        cmd = [build_file]

        logger.info("Executing LLVM build command: %s", cmd)
        self.execute(cmd, cwd=build_dir)

    def _build_llvm_linux64(self, build_dir, prefix, _desc):
        """Build method for llvm on linux"""

        build_env = self.get_current_compiler().get_env()
        tools = self.get_component('tools')

        # Add python to the path:
        build_env['PATH'] = tools.get_tool_dir('python')+":"+build_env['PATH']
        # Add ninja to the path:
        build_env['PATH'] = tools.get_tool_dir('ninja')+":"+build_env['PATH']

        logger.info("Using CXXFLAGS: %s", build_env['CXXFLAGS'])

        cmd = [self.tools.get_cmake_path(), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
               f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DLLVM_TARGETS_TO_BUILD=X86",
               "-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libc;libclc;lld;lldb;openmp;polly;pstl",
               "-DLLVM_ENABLE_EH=ON", "-DLLVM_ENABLE_RTTI=ON",
               "../llvm"]

        build_dir = self.get_path(build_dir, "build")
        self.make_folder(build_dir)

        logger.info("Executing LLVM build command: %s", cmd)
        self.execute(cmd, cwd=build_dir, env=build_env)

        # Build command:
        self.execute([tools.get_ninja_path()], cwd=build_dir, env=build_env)

        # Install command:
        self.execute([tools.get_ninja_path(), "install"], cwd=build_dir, env=build_env)

    # def _build_boost_msvc64(self, build_dir, prefix, desc):
    #     """Build method for boost with msvc64 compiler."""

    #     bs_cmd = ['bootstrap.bat', '--without-icu']
    #     bs_cmd = ['cmd', '/c', " ".join(bs_cmd)]
    #     logger.info("Executing bootstrap command: %s", bs_cmd)
    #     self.execute(bs_cmd, cwd=build_dir)

    #     # Note: updated below to use runtime-link=shared instead of runtime-link=static
    #     bjam_cmd = [build_dir+'/b2.exe', "--prefix="+prefix, "--without-mpi",
    #                 "-sNO_BZIP2=1", "toolset=msvc-14.3", "architecture=x86", "address-model=64", "variant=release",
    #                 "link=static", "threading=multi", "runtime-link=shared", "install"]

    #     logger.info("Executing bjam command: %s", bjam_cmd)
    #     self.execute(bjam_cmd, cwd=build_dir)

    #     # Next we need some cleaning in the installed boost folder, fixing the include path:
    #     # include/boost-1_78/boost -> include/boost
    #     vers = desc['version'].split('.')
    #     bfolder = f"boost-{vers[0]}_{vers[1]}"
    #     src_inc_dir = self.get_path(prefix, "include", bfolder, "boost")
    #     dst_inc_dir = self.get_path(prefix, "include", "boost")
    #     self.move_path(src_inc_dir, dst_inc_dir)
    #     self.remove_folder(self.get_path(prefix, "include", bfolder))

    # def _build_boost_linux64(self, build_dir, prefix, _desc):
    #     """Build method for boost with linux64 compiler."""

    #     comp = self.get_compiler_config()
    #     # cf. https://gist.github.com/Shauren/5c28f646bf7a28b470a8

    #     # Note: the bootstrap.sh script above is crap, so instead we build b2 manually ourself here:
    #     bs_cmd = ["./tools/build/src/engine/build.sh", "clang",
    #               f"--cxx={comp['path']}", f"--cxxflags={comp['cxxflags']}"]
    #     logger.info("Building B2 command: %s", bs_cmd)
    #     self.execute(bs_cmd, cwd=build_dir)
    #     bjam_file = self.get_path(build_dir, "bjam")
    #     self.copy_file(self.get_path(build_dir, "tools/build/src/engine/b2"), bjam_file)
    #     self.add_execute_permission(bjam_file)

    #     with open(os.path.join(build_dir, "user-config.jam"), "w", encoding="utf-8") as file:
    #         # Note: Should not add the -std=c++11 flag below as this will lead to an error with C files:
    #         file.write(f"using clang : : {comp['path']} : ")
    #         file.write(f"<compileflags>\"{comp['cxxflags']} -fPIC\" ")
    #         file.write(f"<linkflags>\"{comp['linkflags']}\" ;\n")

    #     # Note: below we need to run bjam with links to the clang libraries:
    #     build_env = os.environ.copy()
    #     build_env['LD_LIBRARY_PATH'] = comp['library_path']

    #     bjam_cmd = ['./bjam', "--user-config=user-config.jam",
    #                 "--buildid=clang", "-j", "8", "toolset=clang",
    #                 "--prefix="+prefix, "--without-mpi", "-sNO_BZIP2=1",
    #                 "architecture=x86", "variant=release", "link=static", "threading=multi",
    #                 "target-os=linux", "address-model=64", "install"]

    #     logger.info("Executing bjam command: %s", bjam_cmd)
    #     self.execute(bjam_cmd, cwd=build_dir, env=build_env)

    def _build_sdl2_msvc64(self, build_dir, prefix, _desc):
        """Build method for SDL2 with msvc64 compiler."""

        comp = self.get_current_compiler()
        # We write the temp.bat file:
        build_file = build_dir+"/src/build.bat"
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(comp.get_init_script())
            bfile.write(f"{self.tools.get_cmake_path()} -G \"NMake Makefiles\" -DCMAKE_BUILD_TYPE=Release ")
            bfile.write(f"-DCMAKE_CXX_FLAGS_RELEASE=/MT -DSDL_STATIC=ON -DCMAKE_INSTALL_PREFIX=\"{prefix}\" ..\n")
            bfile.write("nmake\n")
            bfile.write("nmake install\n")

        cmd = [build_file]

        logger.info("Executing SDL2 build command: %s", cmd)
        self.execute(cmd, cwd=build_dir+"/src")

    def _build_sdl2_linux64(self, build_dir, prefix, _desc):
        """Build method for sdl2 with linux64 compiler."""

        comp = self.get_current_compiler()
        build_env = comp.get_env()

        logger.info("Using CXXFLAGS: %s", build_env['CXXFLAGS'])

        cmd = [self.tools.get_cmake_path(), "-DCMAKE_BUILD_TYPE=Release", "-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON",
               f"-DCMAKE_INSTALL_PREFIX={prefix}", ".."]

        logger.info("Executing SDL2 build command: %s", cmd)
        self.execute(cmd, cwd=build_dir+"/src", env=build_env)

        # Build command:
        self.execute(["make"], cwd=build_dir+"/src", env=build_env)

        # Install command:
        self.execute(["make", "install"], cwd=build_dir+"/src", env=build_env)

    def _build_luajit_msvc64(self, build_dir, prefix, _desc):
        """Build method for LuaJIT with msvc64 compiler."""

        # First we build the static library, and we install it,
        # and then we will build the shader library and install it
        # because otherwise we get a conflict on the shader/static library name.
        self.make_folder(prefix, "bin")
        self.make_folder(prefix, "include", "luajit")
        self.make_folder(prefix, "lib")

        # replace the /MD flag with /MT:
        self.replace_in_file(build_dir+"/src/msvcbuild.bat", "%LJCOMPILE% /MD /DLUA_BUILD_AS_DLL",
                             "%LJCOMPILE% /MT /DLUA_BUILD_AS_DLL")

        comp = self.get_current_compiler()

        # We write the temp.bat file:
        build_file = build_dir+"/src/build.bat"
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(comp.get_init_script())
            bfile.write("msvcbuild.bat static\n")

        cmd = [build_file]
        logger.debug("Building LuaJIT static version...")
        self.execute(cmd, cwd=build_dir+"/src")

        # install the static library:
        self.copy_file(build_dir+"/src/lua51.lib", prefix+"/lib/lua51_s.lib")
        self.copy_file(build_dir+"/src/luajit.exe", prefix+"/bin/luajit.exe")

        # Now we build the shared library:
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(comp.get_init_script())
            bfile.write("msvcbuild.bat amalg\n")

        cmd = [build_file]

        logger.debug("Building LuaJIT shared version...")
        self.execute(cmd, cwd=build_dir+"/src")

        # Perform the installation manually:
        self.copy_file(build_dir+"/src/lua51.dll", prefix+"/bin/lua51.dll")
        self.copy_file(build_dir+"/src/lua51.lib", prefix+"/lib/lua51.lib")
        self.copy_file(build_dir+"/src/lauxlib.h", prefix+"/include/luajit/lauxlib.h")
        self.copy_file(build_dir+"/src/lua.h", prefix+"/include/luajit/lua.h")
        self.copy_file(build_dir+"/src/lua.hpp", prefix+"/include/luajit/lua.hpp")
        self.copy_file(build_dir+"/src/luaconf.h", prefix+"/include/luajit/luaconf.h")
        self.copy_file(build_dir+"/src/luajit.h", prefix+"/include/luajit/luajit.h")
        self.copy_file(build_dir+"/src/lualib.h", prefix+"/include/luajit/lualib.h")

    def _build_luajit_linux64(self, build_dir, prefix, desc):
        """Build method for luajit with linux64 compiler."""

        comp = self.get_current_compiler()

        # End finally make install:
        build_env = comp.get_env()
        self.execute(["make", "install", f"PREFIX={prefix}", "HOST_CC=clang"], cwd=build_dir, env=build_env)

        # We should rename the include sub folder: "luajit-2.1" -> "luajit"
        dst_name = self.get_path(prefix, "include", "luajit")
        self.rename_folder(f"{dst_name}-{desc['version']}", dst_name)

    def process_command(self, cmd0):
        """Re-implementation of process_command"""

        cmd1 = self.ctx.get_command(1)

        if cmd0 == 'build':
            if cmd1 == "libs":
                self.initialize()
                logger.info("List of settings: %s", self.settings)
                dlist = self.settings['lib_names'].split(',')
                self.check_libraries(dlist)

            if cmd1 is None:
                proj = self.ctx.get_current_project()
                if proj is not None:
                    logger.info("Should build project %s here", proj.get_name())
                    self.get_component('project').build_project(proj)
            return True

        return False
