"""NVP builder class"""

import logging
import re

from nvp.core.build_manager import BuildManager
from nvp.nvp_object import NVPObject

logger = logging.getLogger(__name__)


class NVPBuilder(NVPObject):
    """Simple Builder class"""

    def __init__(self, bman: BuildManager, desc=None):
        """Initialize this builder"""
        self.ctx = bman.ctx
        self.man = bman
        self.compiler = bman.compiler
        self.env = None
        self.install_src_dir = None
        self.install_dst_dir = None
        self.tools = self.ctx.get_component("tools")
        desc = desc or {}
        deftools = ["ninja", "make"] if self.is_windows else ["ninja"]
        self.tool_envs = desc.get("tool_envs", deftools)

    def init_env(self):
        """Init the compiler environment"""
        self.env = self.compiler.get_env()

        # Add the tools to the path:
        tdirs = [self.tools.get_tool_dir(tname) for tname in self.tool_envs]
        self.env = self.prepend_env_list(tdirs, self.env)

        if self.is_linux:
            # We should add the -fPIC flag to the CXXFLAGS:
            flags = self.env.get("CXXFLAGS", "")
            self.env["CXXFLAGS"] = f"{flags} -fPIC"
            flags = self.env.get("CFLAGS", "")
            self.env["CFLAGS"] = f"{flags} -fPIC"

    def build(self, build_dir, prefix, desc):
        """Run the build process either on the proper target platform"""
        self.init_env()

        self.set_install_context(build_dir, prefix)

        if self.is_windows:
            self.build_on_windows(build_dir, prefix, desc)
        elif self.is_linux:
            self.build_on_linux(build_dir, prefix, desc)
        else:
            raise NotImplementedError

    def append_cxxflag(self, val):
        """Append a value to the cxxflags environment var"""
        flags = self.env.get("CXXFLAGS", "")
        self.env["CXXFLAGS"] = f"{flags} {val}"

    def append_cflag(self, val):
        """Append a value to the cflags environment var"""
        flags = self.env.get("CFLAGS", "")
        self.env["CFLAGS"] = f"{flags} {val}"

    def append_ldflag(self, val):
        """Append a value to the ldflags environment var"""
        flags = self.env.get("LDFLAGS", "")
        self.env["LDFLAGS"] = f"{flags} {val}"

    def append_compileflag(self, val):
        """Append a value to both the cxxflags and cflags"""
        self.append_cxxflag(val)
        self.append_cflag(val)

    def append_linkflag(self, val):
        """Append a value to both the ldflags"""
        self.append_ldflag(val)

    def build_on_windows(self, build_dir, prefix, desc):
        """Run the build operation. Should be re-implemented."""
        raise NotImplementedError

    def build_on_linux(self, build_dir, prefix, desc):
        """Run the build operation. Should be re-implemented."""
        raise NotImplementedError

    def check_execute(self, cmd, *args, **kwargs):
        """Run a command and throw if we get an error."""
        res, rcode, _ = self.execute(cmd, *args, **kwargs)
        if res is False:
            self.throw(
                "Error when executing build operation:\nCommand '%s' finished with return code %d.\n=> Stopping build process.",
                cmd,
                rcode,
            )

    def exec_ninja(self, build_dir, flags=None, **kwargs):
        """Run a custom ninja command line"""
        ninja_path = self.tools.get_ninja_path()
        flags = flags or []
        cmd = [ninja_path]
        if self.compiler.is_emcc():
            ext = ".bat" if self.is_windows else ""
            folder = self.compiler.get_cxx_dir()
            emmake_path = self.get_path(folder, f"emmake{ext}")
            cmd = [emmake_path] + cmd

        self.check_execute(cmd + flags, cwd=build_dir, env=self.env, **kwargs)

    def exec_nmake(self, build_dir, flags=None, **kwargs):
        """Run a custom ninja command line"""
        self.check(self.compiler.is_msvc(), "Would only use nmake with MSVC compiler ?")

        folder = self.get_parent_folder(self.compiler.get_cxx_path())
        nmake_path = self.get_path(folder, "nmake.exe")
        flags = flags or []
        self.check_execute([nmake_path] + flags, cwd=build_dir, env=self.env, **kwargs)

    def run_ninja(self, build_dir, flags=None, **kwargs):
        """Execute the standard ninja build/install commands"""
        self.exec_ninja(build_dir, flags=flags, **kwargs)
        self.exec_ninja(build_dir, ["install"], **kwargs)

    def exec_make(self, build_dir, flags=None, **kwargs):
        """Single execution of make"""
        cmd = ["make"]
        if self.compiler.is_msvc():
            # get the full path to make here:
            cmd = [self.tools.get_tool_path("make")]

        if flags is not None:
            cmd += flags

        if self.compiler.is_emcc():
            ext = ".bat" if self.is_windows else ""
            folder = self.compiler.get_cxx_dir()
            emmake_path = self.get_path(folder, f"emmake{ext}")
            cmd = [emmake_path] + cmd

        self.check_execute(cmd, cwd=build_dir, env=self.env, **kwargs)

    def run_make(self, build_dir, **kwargs):
        """Execute the standard make build/install commands"""
        self.exec_make(build_dir)
        self.exec_make(build_dir, ["install"])

    def run_gn(self, build_dir, args, **kwargs):
        """Run gn."""
        python_path = self.tools.get_tool_path("python")
        cmd = [self.tools.get_tool_path("gn"), f"--script-executable={python_path}"] + args

        # logger.info("GN command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env, **kwargs)

    def run_cmake(self, build_dir, prefix, src_dir=None, flags=None, generator="Ninja", **kwargs):
        """Execute Standard cmake configuration command"""
        build_type = kwargs.get("build_type", "Release")
        cmd = [
            self.tools.get_cmake_path(),
            "-G",
            generator,
            f"-DCMAKE_BUILD_TYPE={build_type}",
            f"-DCMAKE_INSTALL_PREFIX={prefix}",
        ]
        if generator == "MinGW Makefiles":
            cmd.append("-DCMAKE_MAKE_PROGRAM=make")

        # Force specifying the compiler:
        # cmd += [f"-DCMAKE_C_COMPILER={self.compiler.get_cc_path()}",
        #         f"-DCMAKE_CXX_COMPILER={self.compiler.get_cxx_path()}"]

        if flags is not None:
            cmd += flags

        # Add the source directory:
        if src_dir is not None:
            cmd.append(src_dir)

        if self.compiler.is_emcc():
            ext = ".bat" if self.is_windows else ""
            folder = self.compiler.get_cxx_dir()
            emcmake_path = self.get_path(folder, f"emcmake{ext}")
            cmd = [emcmake_path] + cmd
            # add -pthread for CXX compilation:
            cmd += ['-DCMAKE_CXX_FLAGS="-pthread"']
            cmd += ['-DCMAKE_C_FLAGS="-pthread"']

        logger.info("Cmake command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env, **kwargs)

    def run_configure(self, build_dir, prefix, flags=None, src_dir=None, configure_name="configure"):
        """Execute Standard configure command"""
        if src_dir is None:
            src_dir = build_dir

        cmd = ["sh", self.get_path(src_dir, configure_name), f"--prefix={prefix}"]
        if flags is not None:
            cmd += flags

        # Check if this is the emcc compiler:
        if self.compiler.is_emcc():
            # Use emconfigure in this case:
            ext = ".bat" if self.is_windows else ""
            folder = self.compiler.get_cxx_dir()
            emconfigure_path = self.get_path(folder, f"emconfigure{ext}")
            cmd = [emconfigure_path] + cmd

        logger.info("configure command: %s", cmd)
        self.check_execute(cmd, cwd=build_dir, env=self.env)

    def patch_file(self, filename, src, dest):
        """Patch the content of a given file"""
        content = self.read_text_file(filename)
        content = content.replace(src, dest)
        self.write_text_file(content, filename)

    def multi_patch_file(self, filename, *changes):
        """Patch the content of a given file"""
        content = self.read_text_file(filename)
        for change in changes:
            content = content.replace(change[0], change[1])
        self.write_text_file(content, filename)

    def set_install_context(self, src_dir=None, dest_dir=None):
        """Set the installation context"""
        self.install_src_dir = src_dir
        self.install_dst_dir = dest_dir

    def install_files(self, src_folder, exp, dst_folder, hint=None, **kwargs):
        """Helper function used to manually install files"""
        self.check(self.install_src_dir is not None, "Invalid installation context src_dir")
        self.check(self.install_dst_dir is not None, "Invalid installation context dst_dir")

        if hint is None:
            hint = "file"

        # Get all the dawn libs:
        base_dir = kwargs.get("src_dir", self.install_src_dir)
        flatten = kwargs.get("flatten", True)
        excluded = kwargs.get("excluded", [])
        included = kwargs.get("included", None)
        recurse = kwargs.get("recurse", False)
        src_dir = self.get_path(base_dir, src_folder)
        all_files = self.get_all_files(src_dir, exp=exp, recursive=recurse)

        dst_dir = self.get_path(self.install_dst_dir, dst_folder)
        self.make_folder(dst_dir)

        res = []

        # copy the dawn libraries:
        for elem in all_files:
            ignored = False
            for pat in excluded:
                if re.search(pat, elem) is not None:
                    ignored = True
                    break

            if included is not None and elem not in included:
                logger.info("Ignoring element %s", elem)
                continue

            if ignored:
                logger.info("Ignoring element %s", elem)
                continue

            logger.info("Installing %s %s", hint, elem)
            src = self.get_path(src_dir, elem)
            dst_file = self.get_filename(src) if flatten else elem
            dst = self.get_path(dst_dir, dst_file)
            pdir = self.get_parent_folder(dst)
            self.make_folder(pdir)

            if self.file_exists(dst):
                self.warn("File %s already exists, removing it.", dst)
                self.remove_file(dst)

            # self.check(not self.file_exists(dst), "File %s already exists.", dst)
            self.copy_file(src, dst)
            res.append(elem)

        return res
