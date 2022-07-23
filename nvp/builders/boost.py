"""This module provide the builder for the boost library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('boost', BoostBuilder(bman))


class BoostBuilder(NVPBuilder):
    """Boost builder class."""

    def build_on_windows(self, build_dir, prefix, desc):
        """Build the boost library on windows"""

        # Note: we always have to use the msvc compiler to do the bootstrap:
        msvc_comp = self.man.get_compiler('msvc')
        msvc_env = msvc_comp.get_env()

        logger.info("Building boost library...")
        bs_cmd = ['bootstrap.bat', '--without-icu']
        bs_cmd = ['cmd.exe', '/c', " ".join(bs_cmd)]
        logger.info("Executing bootstrap command: %s", bs_cmd)
        self.execute(bs_cmd, cwd=build_dir, env=msvc_env)

        if self.compiler.is_clang():
            self.build_with_clang(build_dir, prefix)
        else:
            # Build with MSVC compiler:
            assert self.compiler.is_msvc(), "Expected MSVC compiler here."

            # logger.info("Using build env: %s", self.pretty_print(msvc_env))
            py_path = self.tools.get_tool_path("python").replace("\\", "/")
            py_vers = self.tools.get_tool_desc("python")["version"].split(".")

            with open(self.get_path(build_dir, "user-config.jam"), "w", encoding="utf-8") as file:
                # Add the entry for python:
                file.write(f"using python : {py_vers[0]}.{py_vers[1]} : {py_path} ;\n")

            # Note: updated below to use runtime-link=shared instead of runtime-link=static
            bjam_cmd = [build_dir + '/b2.exe',  "--user-config=user-config.jam", "--prefix=" + prefix,
                        "--without-mpi", "-sNO_BZIP2=1", "toolset=msvc", "architecture=x86",
                        "address-model=64", "variant=release", "link=static", "threading=multi",
                        "runtime-link=shared", "install"]

            logger.info("Executing bjam command: %s", bjam_cmd)
            self.execute(bjam_cmd, cwd=build_dir, env=msvc_env)

        # Next, in both cases we need some cleaning in the installed boost folder, fixing the include path:
        # include/boost-1_78/boost -> include/boost
        vers = desc['version'].split('.')
        bfolder = f"boost-{vers[0]}_{vers[1]}"
        src_inc_dir = self.get_path(prefix, "include", bfolder, "boost")
        dst_inc_dir = self.get_path(prefix, "include", "boost")
        self.move_path(src_inc_dir, dst_inc_dir)
        self.remove_folder(self.get_path(prefix, "include", bfolder))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build the boost library on linux"""

        # compiler should be clang for now:
        assert self.compiler.is_clang(), "Only clang is supported on linux to build boost."
        self.build_with_clang(build_dir, prefix)

    def build_with_clang(self, build_dir, prefix):
        """Build with the clang compiler"""

        logger.info("Building boost library...")

        build_env = self.compiler.get_env()
        # logger.info("Using build env: %s", self.pretty_print(build_env))

        comp_path = self.compiler.get_cxx_path()
        cxxflags = self.compiler.get_cxxflags()
        linkflags = self.compiler.get_linkflags()

        ext = ".exe" if self.is_windows else ""

        if self.is_linux:
            # Note: the bootstrap.sh script above is crap, so instead we build b2 manually ourself here:
            script_file = self.get_path(build_dir, f"./tools/build/src/engine/build.sh")
            bs_cmd = [script_file, "clang", f"--cxx={comp_path}", f"--cxxflags={cxxflags}"]

            logger.info("Building B2 command: %s", bs_cmd)
            self.execute(bs_cmd, cwd=build_dir)
            bjam_file = self.get_path(build_dir, f"b2{ext}")
            self.copy_file(self.get_path(build_dir, f"tools/build/src/engine/b2{ext}"), bjam_file)
            self.add_execute_permission(bjam_file)

        # for windows:
        # cf. https://gist.github.com/oxycoder/98864df68f7a879066c51c181a492fe2
        # Ensure we use backslashes:
        comp_dir = self.compiler.get_cxx_dir().replace("\\", "/")
        comp_path = comp_path.replace("\\", "/")

        py_path = self.tools.get_tool_path("python").replace("\\", "/")
        py_vers = self.tools.get_tool_desc("python")["version"].split(".")

        ver_major = self.compiler.get_major_version()
        ver_minor = self.compiler.get_minor_version()

        with open(self.get_path(build_dir, "user-config.jam"), "w", encoding="utf-8") as file:
            # Note: Should not add the -std=c++11 flag below as this will lead to an error with C files:
            file.write(f"using clang : {ver_major}.{ver_minor} : {comp_path} : ")
            if self.is_windows:
                file.write("cxxstd=17 ")
                file.write(f"<ranlib>\"{comp_dir}/llvm-ranlib.exe\" ")
                file.write(f"<archiver>\"{comp_dir}/llvm-ar.exe\" ")
                file.write("<cxxflags>\"-D_CRT_SECURE_NO_WARNINGS -D_MT -D_DLL -Xclang --dependent-lib=msvcrt\" ")
                # file.write(f"<cxxflags>-D_SILENCE_CXX17_OLD_ALLOCATOR_MEMBERS_DEPRECATION_WARNING ")
                file.write(";\n")
            else:
                file.write(f"<compileflags>\"{cxxflags} -fPIC\" ")
                file.write(f"<linkflags>\"{linkflags}\" ;\n")

            # Add the entry for python:
            file.write(f"using python : {py_vers[0]}.{py_vers[1]} : {py_path} ;\n")

            # "--with-python="+pyPath+"/bin/python3", "--with-python-root="+pyPath

        # Note: below we need to run bjam with links to the clang libraries:
        bjam = self.get_path(build_dir, f'./b2{ext}')
        # tgt_os = "windows" if self.is_windows else "linux"
        # f"target-os={tgt_os}",
        # "--buildid=clang",
        bjam_cmd = [bjam, "--user-config=user-config.jam",
                    "-j", "8", "toolset=clang",
                    "--prefix="+prefix, "--without-mpi", "-sNO_BZIP2=1",
                    "architecture=x86", "variant=release", "link=static", "threading=multi",
                    "address-model=64"]
        if self.is_windows:
            bjam_cmd.append("runtime-link=shared")

        bjam_cmd.append("install")

        logger.info("Executing bjam command: %s", bjam_cmd)
        self.execute(bjam_cmd, cwd=build_dir, env=build_env)
