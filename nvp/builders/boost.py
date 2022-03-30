"""This module provide the builder for the boost library."""

import logging

from nvp.components.build import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('boost', BoostBuilder(bman))


class BoostBuilder(NVPBuilder):
    """Boost builder class."""

    def build_on_windows(self, build_dir, prefix, desc):
        """Build the boost library on windows"""

        if self.compiler.is_clang():
            self.build_with_clang(build_dir, prefix)
            return

        # build with msvc:
        assert self.compiler.is_msvc(), "Expected MSVC compiler here."
        logger.info("Building boost library...")

        build_env = self.compiler.get_env()
        # logger.info("Using build env: %s", self.pretty_print(build_env))

        bs_cmd = ['bootstrap.bat', '--without-icu']
        bs_cmd = ['cmd.exe', '/c', " ".join(bs_cmd)]
        logger.info("Executing bootstrap command: %s", bs_cmd)
        self.execute(bs_cmd, cwd=build_dir, env=build_env)

        # Note: updated below to use runtime-link=shared instead of runtime-link=static
        bjam_cmd = [build_dir + '/b2.exe', "--prefix=" + prefix, "--without-mpi", "-sNO_BZIP2=1",
                    f"toolset=msvc", "architecture=x86", "address-model=64", "variant=release",
                    "link=static", "threading=multi", "runtime-link=shared", "install"]

        logger.info("Executing bjam command: %s", bjam_cmd)
        self.execute(bjam_cmd, cwd=build_dir, env=build_env)

        # Next we need some cleaning in the installed boost folder, fixing the include path:
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

        # Note: the bootstrap.sh script above is crap, so instead we build b2 manually ourself here:
        sh_ext = "bat" if self.is_windows else "sh"
        ext = ".exe" if self.is_windows else ""
        script_file = self.get_path(build_dir, f"./tools/build/src/engine/build.{sh_ext}")
        bs_cmd = [script_file, "clang",
                  f"--cxx={comp_path}", f"--cxxflags={cxxflags}"]

        logger.info("Building B2 command: %s", bs_cmd)
        self.execute(bs_cmd, cwd=build_dir)
        bjam_file = self.get_path(build_dir, f"bjam{ext}")
        self.copy_file(self.get_path(build_dir, f"tools/build/src/engine/b2{ext}"), bjam_file)
        self.add_execute_permission(bjam_file)

        with open(self.get_path(build_dir, "user-config.jam"), "w", encoding="utf-8") as file:
            # Note: Should not add the -std=c++11 flag below as this will lead to an error with C files:
            file.write(f"using clang : : {comp_path} : ")
            file.write(f"<compileflags>\"{cxxflags} -fPIC\" ")
            file.write(f"<linkflags>\"{linkflags}\" ;\n")

        # Note: below we need to run bjam with links to the clang libraries:
        bjam = self.get_path(build_dir, f'./bjam{ext}')
        bjam_cmd = [bjam, "--user-config=user-config.jam",
                    "--buildid=clang", "-j", "8", "toolset=clang",
                    "--prefix="+prefix, "--without-mpi", "-sNO_BZIP2=1",
                    "architecture=x86", "variant=release", "link=static", "threading=multi",
                    "target-os=linux", "address-model=64", "install"]

        logger.info("Executing bjam command: %s", bjam_cmd)
        self.execute(bjam_cmd, cwd=build_dir, env=build_env)
