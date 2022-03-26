"""This module provide the builder for the boost library."""

import logging

from nvp.components.build import BuildManager

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""
    bman.register_builder()


def build_library(bman: BuildManager, compiler, build_dir, prefix, desc):
    """Build the boost library"""

    benv = compiler.get_env()

    if bman.is_windows:
        bs_cmd = ['bootstrap.bat', '--without-icu']
        bs_cmd = ['cmd', '/c', " ".join(bs_cmd)]
        logger.info("Executing bootstrap command: %s", bs_cmd)
        bman.execute(bs_cmd, cwd=build_dir, env=benv)

        # Note: updated below to use runtime-link=shared instead of runtime-link=static
        # toolset should be msvc-14.3
        bjam_cmd = [build_dir + '/b2.exe', "--prefix=" + prefix, "--without-mpi", "-sNO_BZIP2=1",
                    f"toolset={compiler.get_code_name()}", "architecture=x86", "address-model=64", "variant=release",
                    "link=static", "threading=multi", "runtime-link=shared", "install"]

        logger.info("Executing bjam command: %s", bjam_cmd)
        bman.execute(bjam_cmd, cwd=build_dir)

        # Next we need some cleaning in the installed boost folder, fixing the include path:
        # include/boost-1_78/boost -> include/boost
        vers = desc['version'].split('.')
        bfolder = f"boost-{vers[0]}_{vers[1]}"
        src_inc_dir = bman.get_path(prefix, "include", bfolder, "boost")
        dst_inc_dir = bman.get_path(prefix, "include", "boost")
        bman.move_path(src_inc_dir, dst_inc_dir)
        bman.remove_folder(bman.get_path(prefix, "include", bfolder))

    elif bman.is_linux:
        # compiler should be clang for now:
        assert compiler.is_clang(), "Only clang is supported on linux to build boost."

        comp_path = compiler.get_cxx_path()
        cxxflags = compiler.get_cxxflags()
        linkflags = compiler.get_linkflags()

        # Note: the bootstrap.sh script above is crap, so instead we build b2 manually ourself here:
        bs_cmd = ["./tools/build/src/engine/build.sh", "clang",
                  f"--cxx={comp_path}", f"--cxxflags={cxxflags}"]

        logger.info("Building B2 command: %s", bs_cmd)
        bman.execute(bs_cmd, cwd=build_dir)
        bjam_file = bman.get_path(build_dir, "bjam")
        bman.copy_file(bman.get_path(build_dir, "tools/build/src/engine/b2"), bjam_file)
        bman.add_execute_permission(bjam_file)

        with open(bman.get_path(build_dir, "user-config.jam"), "w", encoding="utf-8") as file:
            # Note: Should not add the -std=c++11 flag below as this will lead to an error with C files:
            file.write(f"using clang : : {comp_path} : ")
            file.write(f"<compileflags>\"{cxxflags} -fPIC\" ")
            file.write(f"<linkflags>\"{linkflags}\" ;\n")

        # Note: below we need to run bjam with links to the clang libraries:
        bjam_cmd = ['./bjam', "--user-config=user-config.jam",
                    "--buildid=clang", "-j", "8", "toolset=clang",
                    "--prefix="+prefix, "--without-mpi", "-sNO_BZIP2=1",
                    "architecture=x86", "variant=release", "link=static", "threading=multi",
                    "target-os=linux", "address-model=64", "install"]

        logger.info("Executing bjam command: %s", bjam_cmd)
        bman.execute(bjam_cmd, cwd=build_dir, env=benv)
