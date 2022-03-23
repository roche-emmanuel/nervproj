"""Module for build management system"""

import os
import sys
import logging
import requests

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

        desc = {
            "tools": {"install": None},
            "build": {"libs": None},
        }
        ctx.define_subparsers("main", desc)
        psr = ctx.get_parser('main.build.libs')
        psr.add_argument("lib_names", type=str, nargs='?', default="all",
                         help="List of library names that we should build")

        # Setup the paths:
        self.setup_paths()

        self.msvc_setup_path = None
        self.tool_paths = {}

        # if self.settings.get('install_python_requirements', False):
        #     self.install_python_requirements()

        # if self.settings.get('check_deps', None) is not None:
        #     dlist = self.settings['check_deps'].split(',')
        #     self.check_libraries(dlist)

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.setup_flavor()
            self.setup_tools()
            self.initialized = True

    def setup_flavor(self):
        """Setup the target flavor depending on the current platform we are on."""

        if self.flavor == "msvc64":
            # read the env variable:
            self.msvc_setup_path = os.getenv('NVL_MSVC_SETUP')

            # get the list of paths from the build_config:
            if self.msvc_setup_path is None:
                potential_paths = self.config.get('msvc_install_paths', [])
                for vc_path in potential_paths:
                    setup_path = self.get_path(vc_path, "VC/Auxiliary/Build/vcvarsall.bat")

                    if os.path.exists(setup_path):
                        logger.info("Using MSVC setup path %s", setup_path)
                        self.msvc_setup_path = setup_path
                        break

            if self.msvc_setup_path is None:
                raise RuntimeError("MSVC setup path not found.")

    def setup_paths(self):
        """Setup the paths that will be used during build or run process."""

        # Store the deps folder:
        base_dir = self.ctx.get_root_dir()
        self.tools_dir = self.get_path(base_dir, "tools", self.platform)
        self.libs_dir = self.make_folder(base_dir, "libraries", self.flavor)
        self.libs_build_dir = self.make_folder(base_dir, "libraries", "build")
        self.libs_package_dir = self.make_folder(base_dir, "libraries", self.flavor)

    def setup_tools(self):
        """Setup all the tools on this platform."""
        # Prepare the tool paths:
        tools = self.config[f'{self.platform}_tools']

        for desc in tools:
            tname = desc['name']
            if 'path' in desc:
                # logger.debug("Using system path '%s' for %s tool", desc['path'], tname)
                self.tool_paths[tname] = desc['path']
            else:
                full_name = f"{tname}-{desc['version']}"
                install_path = self.get_path(self.tools_dir, full_name)
                tpath = self.get_path(install_path, desc['sub_path'])
                if not self.file_exists(tpath):

                    # retrieve the most appropriate source package for that tool:
                    pkg_file = self.retrieve_tool_package(desc)

                    # Extract the package:
                    self.extract_package(pkg_file, self.tools_dir, rename=full_name)

                    # CHeck if we have a post install command:
                    fname = f"_post_install_{desc['name']}_{self.platform}"
                    postinst = self.get_method(fname.lower())
                    if postinst is not None:
                        logger.info("Running post install for %s...", full_name)
                        postinst(install_path, desc)

                    # Remove the source package:
                    # self.remove_file(pkg_file)

                # The tool path should really exist now:
                assert self.file_exists(tpath), f"No valid package provided for {full_name}"

                # Store the tool path:
                self.tool_paths[tname] = tpath

                # Ensure the execution permission is set:
                self.add_execute_permission(self.tool_paths[tname])

    def retrieve_tool_package(self, desc):
        """Retrieve the most appropriate package for a given tool and
        store it in a local folder for extraction."""

        # Tool packages can be searched with "per tool" urls, of inside the package urls.
        # priority shoould be given to per "tool url" if available:

        urls = desc.get("urls", [])

        # Next we should extend with the package urls:
        full_name = f"{desc['name']}-{desc['version']}"

        # add support for ".7z" or ".tar.xz" archives:
        canonical_pkg_name = f"tools/{full_name}-{self.platform}"
        extensions = [".7z", ".tar.xz"]
        pkg_urls = self.config.get("package_urls", [])
        pkg_urls = [base_url+canonical_pkg_name+ext for base_url in pkg_urls for ext in extensions]

        if self.config.get("prioritize_package_urls", False):
            urls = pkg_urls + urls
        else:
            urls = urls + pkg_urls

        # Next we select the first valid URL:
        url = self.ctx.select_first_valid_path(urls)
        logger.info("Retrieving package for %s from url %s", full_name, url)

        filename = os.path.basename(url)

        # We download the file directly into the tools_dir as we don't want to
        tgt_pkg_path = self.get_path(self.tools_dir, filename)

        if not self.file_exists(tgt_pkg_path):
            # Download that file locally:
            self.download_file(url, tgt_pkg_path)
        else:
            logger.info("Using already downloaded package source %s", tgt_pkg_path)

        pkg_file = tgt_pkg_path
        logger.debug("Using source package %s for %s", pkg_file, full_name)

        return pkg_file

    def get_tool_desc(self, tname):
        """Retrieve the description dic for a given tool by name"""

        tools = self.config[f'{self.platform}_tools']
        for desc in tools:
            if desc['name'] == tname:
                return desc

        logger.warning("Cannot find tool desc for %s", tname)
        return None

    def get_unzip_path(self):
        """Retrieve unzip tool path."""
        return self.tool_paths['7zip']

    def get_cmake_path(self):
        """Retrieve xmake tool path."""
        return self.tool_paths['cmake']

    def get_git_path(self):
        """Retrieve git tool path."""
        return self.tool_paths['git']

    def get_compiler_config(self):
        """Get compiler config as a dict"""

        if self.platform == "windows":
            return {
                "name": "msvc"
            }

        desc = self.get_tool_desc("clang")
        fpath = self.tool_paths['clang']
        bpath = self.get_path(self.tools_dir, f"{desc['name']}-{desc['version']}")
        return {
            "name": "clang",
            "file": "clang++",
            "path": fpath,
            "dir": os.path.dirname(fpath),
            "base_path": bpath,
            "library_path": self.get_path(bpath, "lib"),
            # "cxxflags": "-stdlib=libc++ -nodefaultlibs -lc++ -lc++abi -lm -lc -lgcc_s -lpthread"
            "cxxflags": "-stdlib=libc++ -w",
            "linkflags": "-stdlib=libc++ -nodefaultlibs -lc++ -lc++abi -lm -lc -lgcc_s -lpthread"
        }

    def setup_compiler_env(self, env=None):
        """Setup an environment using the current compiler config."""

        if env is None:
            env = os.environ.copy()

        comp = self.get_compiler_config()

        env['PATH'] = comp['dir']+":"+env['PATH']

        inc_dir = f"{comp['base_path']}/include/c++/v1"

        env['CC'] = comp['dir']+'/clang'
        env['CXX'] = comp['dir']+'/clang++'
        env['CXXFLAGS'] = f"-I{inc_dir} {comp['cxxflags']} -fPIC"
        env['CFLAGS'] = f"-I{inc_dir} -w -fPIC"

        return env

    def install_python_requirements(self):
        """Install the requirements for the main python environment using pip"""

        logger.info("Installing python requirements...")
        reqfile = self.get_path(self.ctx.get_root_dir(), "tools/requirements.txt")
        cmd = [sys.executable, "-m", "pip", "install", "-r", reqfile]
        # logger.info("Executing command: %s", cmd)
        self.execute(cmd)
        logger.info("Done installing python requirements.")

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

    def deploy_dependency(self, desc):
        """Build a given dependency given its description dict and the target
        directory where it should be installed."""

        dep_name = self.get_std_package_name(desc)
        src_pkg_name = f"{dep_name}-{self.flavor}.7z"

        # Here we should check if we already have a pre-built package for that dependency:
        src_pkg_path = self.get_path(self.libs_package_dir, src_pkg_name)

        # if the package is not already available locally, maybe we can retrieve it remotely:
        if not self.file_exists(src_pkg_path):
            pkg_urls = self.config.get("package_urls", [])
            pkg_urls = [base_url+'libraries/'+src_pkg_name for base_url in pkg_urls]

            pkg_url = self.ctx.select_first_valid_path(pkg_urls)
            if pkg_url is not None:
                self.download_file(pkg_url, src_pkg_path)

        if self.file_exists(src_pkg_path):
            # We should simply extract that package into our target dir:
            self.extract_package(src_pkg_path, self.libs_dir, rename=dep_name)
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

    def extract_package(self, src_pkg_path, dest_dir, rename=None):
        """Extract source package into the target dir folder."""

        logger.info("Extracting %s...", src_pkg_path)

        # check what is our expected extracted name:
        cur_name = self.remove_file_extension(os.path.basename(src_pkg_path))

        expected_name = cur_name if rename is None else rename
        dst_dir = self.get_path(dest_dir, expected_name)
        src_dir = self.get_path(dest_dir, cur_name)

        # Ensure that the destination/source folders do not exists:
        assert not self.path_exists(dst_dir), f"Unexpected existing path: {dst_dir}"
        assert not self.path_exists(src_dir), f"Unexpected existing path: {src_dir}"

        # check if this is a tar.xz archive:
        if src_pkg_path.endswith(".tar.xz"):
            cmd = ["tar", "-xvJf", src_pkg_path, "-C", dest_dir]
        elif src_pkg_path.endswith(".tar.gz") or src_pkg_path.endswith(".tgz"):
            cmd = ["tar", "-xvzf", src_pkg_path, "-C", dest_dir]
        elif src_pkg_path.endswith(".7z.exe"):
            cmd = [self.get_unzip_path(), "x", "-o"+dest_dir+"/"+expected_name, src_pkg_path]
        else:
            cmd = [self.get_unzip_path(), "x", "-o"+dest_dir, src_pkg_path]
        self.execute(cmd, self.settings['verbose'])

        # Check if renaming is necessary:
        if not self.path_exists(dst_dir):
            assert self.path_exists(src_dir), f"Missing extracted path {src_dir}"
            logger.debug("Renaming folder %s to %s", cur_name, rename)
            self.rename_folder(src_dir, dst_dir)

        logger.debug("Done extracting package.")

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

        cmd = [self.get_unzip_path(), "a", "-t7z", self.get_path(dest_folder, package_name), src_path,
               "-m0=lzma2", "-mx=9", "-aoa", "-mfb=64",
               "-md=32m", "-ms=on", "-r"]
        self.execute(cmd, self.settings['verbose'])
        logger.debug("Done generating package %s", package_name)
        return True

    def setup_dependency_build_context(self, desc):
        """Prepare the build folder for a given dependency package
        We then return the build_dir, dep_name and target install prefix"""

        # First we need to download the source package if missing:
        base_build_dir = self.libs_build_dir

        # get the filename from the url:
        url = desc['url']
        filename = os.path.basename(url)

        # Note that at this point the url may be a git path.
        # so filename will be "reponame.git" for instance
        src_pkg = self.get_path(base_build_dir, filename)

        from_git = url.startswith("git@")
        # once the source file is downloaded we should extract it:
        build_dir = src_pkg if from_git else os.path.splitext(src_pkg)[0]

        # remove the previous source content if any:
        logger.info("Removing previous source folder %s", build_dir)
        self.remove_folder(build_dir)

        # download file if needed:
        if not os.path.exists(src_pkg):
            self.download_file(url, src_pkg)

        # Now extract the source folder:
        if not from_git:
            self.extract_package(src_pkg, base_build_dir)

        dep_name = self.get_std_package_name(desc)
        prefix = self.get_path(self.libs_dir, dep_name)

        return (build_dir, prefix, dep_name)

    #############################################################################################
    # Builder functions:
    #############################################################################################

    def _build_boost_msvc64(self, build_dir, prefix, desc):
        """Build method for boost with msvc64 compiler."""

        bs_cmd = ['bootstrap.bat', '--without-icu']
        bs_cmd = ['cmd', '/c', " ".join(bs_cmd)]
        logger.info("Executing bootstrap command: %s", bs_cmd)
        self.execute(bs_cmd, cwd=build_dir)

        bjam_cmd = [build_dir+'/b2.exe', "--prefix="+prefix, "--without-mpi",
                    "-sNO_BZIP2=1", "toolset=msvc-14.3", "architecture=x86", "address-model=64", "variant=release",
                    "link=static", "threading=multi", "runtime-link=static", "install"]

        logger.info("Executing bjam command: %s", bjam_cmd)
        self.execute(bjam_cmd, cwd=build_dir)

        # Next we need some cleaning in the installed boost folder, fixing the include path:
        # include/boost-1_78/boost -> include/boost
        vers = desc['version'].split('.')
        bfolder = f"boost-{vers[0]}_{vers[1]}"
        src_inc_dir = self.get_path(prefix, "include", bfolder, "boost")
        dst_inc_dir = self.get_path(prefix, "include", "boost")
        self.move_path(src_inc_dir, dst_inc_dir)
        self.remove_folder(self.get_path(prefix, "include", bfolder))

    def _build_boost_linux64(self, build_dir, prefix, _desc):
        """Build method for boost with linux64 compiler."""

        comp = self.get_compiler_config()
        # cf. https://gist.github.com/Shauren/5c28f646bf7a28b470a8

        # Note: the bootstrap.sh script above is crap, so instead we build b2 manually ourself here:
        bs_cmd = ["./tools/build/src/engine/build.sh", "clang",
                  f"--cxx={comp['path']}", f"--cxxflags={comp['cxxflags']}"]
        logger.info("Building B2 command: %s", bs_cmd)
        self.execute(bs_cmd, cwd=build_dir)
        bjam_file = self.get_path(build_dir, "bjam")
        self.copy_file(self.get_path(build_dir, "tools/build/src/engine/b2"), bjam_file)
        self.add_execute_permission(bjam_file)

        with open(os.path.join(build_dir, "user-config.jam"), "w", encoding="utf-8") as file:
            # Note: Should not add the -std=c++11 flag below as this will lead to an error with C files:
            file.write(f"using clang : : {comp['path']} : ")
            file.write(f"<compileflags>\"{comp['cxxflags']} -fPIC\" ")
            file.write(f"<linkflags>\"{comp['linkflags']}\" ;\n")

        # Note: below we need to run bjam with links to the clang libraries:
        build_env = os.environ.copy()
        build_env['LD_LIBRARY_PATH'] = comp['library_path']

        bjam_cmd = ['./bjam', "--user-config=user-config.jam",
                    "--buildid=clang", "-j", "8", "toolset=clang",
                    "--prefix="+prefix, "--without-mpi", "-sNO_BZIP2=1",
                    "architecture=x86", "variant=release", "link=static", "threading=multi",
                    "target-os=linux", "address-model=64", "install"]

        logger.info("Executing bjam command: %s", bjam_cmd)
        self.execute(bjam_cmd, cwd=build_dir, env=build_env)

    def _build_sdl2_msvc64(self, build_dir, prefix, _desc):
        """Build method for SDL2 with msvc64 compiler."""

        # We write the temp.bat file:
        build_file = build_dir+"/src/build.bat"
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(f"call {self.msvc_setup_path} amd64\n")
            bfile.write(f"{self.get_cmake_path()} -G \"NMake Makefiles\" -DCMAKE_BUILD_TYPE=Release ")
            bfile.write(f"-DCMAKE_CXX_FLAGS_RELEASE=/MT -DSDL_STATIC=ON -DCMAKE_INSTALL_PREFIX=\"{prefix}\" ..\n")
            bfile.write("nmake\n")
            bfile.write("nmake install\n")

        cmd = [build_file]

        logger.info("Executing SDL2 build command: %s", cmd)
        self.execute(cmd, cwd=build_dir+"/src")

    def _build_sdl2_linux64(self, build_dir, prefix, _desc):
        """Build method for sdl2 with linux64 compiler."""

        build_env = self.setup_compiler_env()

        logger.info("Using CXXFLAGS: %s", build_env['CXXFLAGS'])

        cmd = [self.get_cmake_path(), "-DCMAKE_BUILD_TYPE=Release", "-DSDL_STATIC=ON", "-DSDL_STATIC_PIC=ON",
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

        # We write the temp.bat file:
        build_file = build_dir+"/src/build.bat"
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(f"call {self.msvc_setup_path} amd64\n")
            bfile.write("msvcbuild.bat static\n")

        cmd = [build_file]
        logger.debug("Building LuaJIT static version...")
        self.execute(cmd, cwd=build_dir+"/src")

        # install the static library:
        self.copy_file(build_dir+"/src/lua51.lib", prefix+"/lib/lua51_s.lib")
        self.copy_file(build_dir+"/src/luajit.exe", prefix+"/bin/luajit.exe")

        # Now we build the shared library:
        with open(build_file, 'w', encoding="utf-8") as bfile:
            bfile.write(f"call {self.msvc_setup_path} amd64\n")
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

        # End finally make install:
        build_env = self.setup_compiler_env()
        self.execute(["make", "install", f"PREFIX={prefix}", "HOST_CC=clang"], cwd=build_dir, env=build_env)

        # We should rename the include sub folder: "luajit-2.1" -> "luajit"
        dst_name = self.get_path(prefix, "include", "luajit")
        self.rename_folder(f"{dst_name}-{desc['version']}", dst_name)

    def _post_install_git_windows(self, install_path, _desc):
        """Run post install for portable git on windows"""

        # There should be a "post-install.bat" script in the install folder:
        sfile = self.get_path(install_path, "post-install.bat")
        assert self.file_exists(sfile), "No post-install.bat script found."

        # We should not delete that file automatically at this end of it,
        # as this would trigger an error:
        self.replace_in_file(sfile, "@DEL post-install.bat", "")

        cmd = [self.get_path(install_path, "git-cmd.exe"), "--no-needs-console",
               "--hide", "--no-cd", "--command=post-install.bat"]

        logger.info("Executing command: %s", cmd)
        self.execute(cmd, cwd=install_path, verbose=True)

        # Finally we remove the script file:
        self.remove_file(sfile)

    def download_file(self, url, dest_file):
        """Helper function used to download a file with progress report."""

        if url.startswith("git@"):
            logger.info("Checking out git repo %s...", url)
            cmd = [self.get_git_path(), "clone", url, dest_file]
            self.execute(cmd)
            return

        # Check if this is a valid local file:
        if self.file_exists(url):
            # Just copy the file in that case:
            logger.info("Copying file from %s...", url)
            self.copy_file(url, dest_file, True)
            return

        logger.info("Downloading file from %s...", url)
        with open(dest_file, "wb") as fdd:
            response = requests.get(url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                fdd.write(response.content)
            else:
                dlsize = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dlsize += len(data)
                    fdd.write(data)
                    frac = dlsize / total_length
                    done = int(50 * frac)
                    sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {dlsize}/{total_length} {frac*100:.3f}%")
                    sys.stdout.flush()

                sys.stdout.write('\n')
                sys.stdout.flush()

    def process_command(self, cmd0):
        """Re-implementation of process_command"""

        cmd1 = self.ctx.get_command(1)
        if cmd0 == 'tools':
            if cmd1 == "install":
                self.initialize()

            return True

        if cmd0 == 'build':
            if cmd1 == "libs":
                self.initialize()
                logger.info("List of settings: %s", self.settings)
                dlist = self.settings['lib_names'].split(',')
                self.check_libraries(dlist)

            return True

        return False
