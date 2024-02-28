"""This module contains a definition of a compiler class for NVP"""

# from __future__ import print_function
import logging
import os
import subprocess

from nvp.nvp_object import NVPObject

logger = logging.getLogger(__name__)

# cf. https://stackoverflow.com/questions/1214496/how-to-get-environment-from-a-subprocess


def get_environment_from_batch_command(env_cmd, initial=None):
    """
    Take a command (either a single command or list of arguments)
    and return the environment created after running that command.
    Note that if the command must be a batch file or .cmd file, or the
    changes to the environment will not be captured.

    If initial is supplied, it is used as the initial environment passed
    to the child process.
    """
    if not isinstance(env_cmd, (list, tuple)):
        env_cmd = [env_cmd]
    # construct the command that will alter the environment
    env_cmd = subprocess.list2cmdline(env_cmd)
    # create a tag so we can tell in the output when the proc is done
    tag = "------------- ENV VARS -------------"
    # construct a cmd.exe command to do accomplish this
    cmd = f'cmd.exe /s /c "{env_cmd} && echo {tag} && set"'
    # cmd = ["cmd.exe", "/s", "/s", f'\"{env_cmd} && echo "{tag}" && set\"']

    # launch the process
    # logger.info("Executing command: %s", cmd)
    # out = subprocess.check_output(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=initial)
    out = proc.communicate()[0].decode("utf-8")
    # logger.info("Retrieved whole outputs: %s", out)

    # Split the outputs on the lines:
    lines = out.splitlines()
    while lines[0].rstrip() != tag:
        # logger.info("Dropping line %s", lines[0])
        lines.pop(0)

    # Drop the tag line:
    lines.pop(0)

    # Now parse each line into an environment KEY=VALUE pair:
    result = {}
    for line in lines:
        parts = line.split("=")
        assert len(parts) == 2, f"Cannot parse environment variable line '{line}'"
        result[parts[0]] = parts[1]

    # logger.info("Collected MSVC full environment: %s", result)
    return result


class NVPCompiler(NVPObject):
    """A class representing a compiler"""

    def __init__(self, ctx, desc):
        """Compiler class constructor"""
        assert "type" in desc, "Invalid compiler type"
        self.ctx = ctx
        self.desc = desc
        self.type = desc["type"]
        self.linkflags = None
        self.libs_path = None
        self.version = None
        self.version_major = None
        self.version_minor = None
        self.cxx_path = None
        self.cc_path = None
        self.comp_env = None

        ext = ".exe" if self.is_windows else ""

        if self.type == "msvc":
            # This compiler must always be available:
            setup_file = desc["setup_path"]
            assert self.file_exists(setup_file), f"Invalid MSVC setup path: {setup_file}"
            # setup is: VC/Auxiliary/Build/vcvarsall.bat
            self.root_dir = self.get_parent_folder(setup_file)  # Build dir
            # We read the VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt file to get the version number
            vers_file = self.get_path(self.root_dir, "Microsoft.VCToolsVersion.default.txt")
            assert self.file_exists(vers_file), f"Invalid MSVC version file: {vers_file}"
            self.version = self.read_text_file(vers_file).rstrip()

            self.root_dir = self.get_parent_folder(self.root_dir)  # Aux dir
            self.root_dir = self.get_parent_folder(self.root_dir)  # VC dir
            self.root_dir = self.get_parent_folder(self.root_dir)  # root dir
            logger.info("MSVC root dir is: %s", self.root_dir)

            # example: D:\Softs\VisualStudio\VS2022\VC\Tools\MSVC\14.34.31933\bin\Hostx64\x64
            self.cxx_path = self.get_path(
                self.root_dir, "VC", "Tools", "MSVC", self.version, "bin", "Hostx64", "x64", "cl.exe"
            )
            self.cc_path = self.cxx_path
        elif self.type == "emcc":
            ext2 = ".bat" if self.is_windows else ""
            self.root_dir = desc["root_dir"]
            self.cxx_path = self.get_path(self.root_dir, "em++" + ext2)
            self.cc_path = self.get_path(self.root_dir, "emcc" + ext2)
            self.libs_path = self.get_path(self.root_dir, "lib")
            self.linkflags = ""
            self.version = "3.1.35"
        else:
            assert self.type == "clang", f"No support for compiler type {self.type}"
            self.root_dir = desc["root_dir"]

            self.cxx_path = self.get_path(self.root_dir, "bin", "clang++" + ext)
            self.cc_path = self.get_path(self.root_dir, "bin", "clang" + ext)
            self.libs_path = self.get_path(self.root_dir, "lib")

            # self.cxxflags = "-stdlib=libc++ -nodefaultlibs -lc++ -lc++abi -lm -lc -lgcc_s -lpthread"
            self.linkflags = ""
            # self.cxxflags = "-stdlib=libc++ -w"
            # self.linkflags = "-stdlib=libc++ -nodefaultlibs -lc++ -lc++abi -lm -lc -lgcc_s -lpthread"

            # extract the version number from the root_dir:
            parts = self.root_dir.split("-")
            assert len(parts) >= 2, f"Invalid root dir format for compiler {self.root_dir}"
            self.version = parts[-1]

        parts = self.version.split(".")
        assert len(parts) == 3, f"Invalid compiler version {self.version}"
        self.version_major = int(parts[0])
        self.version_minor = int(parts[1])
        self.version_release = int(parts[2]) if len(parts) >= 3 else 0
        logger.debug("Found %s-%s", self.type, self.version)

    def get_type(self):
        """Return this compiler type"""
        return self.desc["type"]

    def is_msvc(self):
        """Check if this is an MSVC compiler"""
        return self.get_type() == "msvc"

    def is_clang(self):
        """Check if this is a clang compiler"""
        return self.get_type() == "clang"

    def is_emcc(self):
        """Check if this is a emscripten compiler"""
        return self.get_type() == "emcc"

    def is_available(self):
        """Check if this compiler is currently available."""
        if self.type == "msvc":
            return True

        return self.file_exists(self.get_cxx_path())

    def get_weight(self):
        """Retrive the weight of this compiler."""
        if not self.is_available():
            return 0

        # Compiler is available:
        return self.get_major_version() * 1000 + self.get_minor_version()

    def get_cxxflags(self):
        """Retrieve the cxxflags"""
        return self.comp_env.get("CXXFLAGS", "")

    def get_linkflags(self):
        """Retrieve the linkflags"""
        return self.comp_env.get("LDFLAGS", "")

    def get_major_version(self):
        """Retrive major version as int"""
        return self.version_major

    def get_minor_version(self):
        """Retrive minor version as int"""
        return self.version_minor

    def get_root_dir(self):
        """Retrieve root dir"""
        return self.root_dir

    def get_cxx_dir(self):
        """Retrieve root dir"""
        return self.get_parent_folder(self.cxx_path)

    def get_cxx_path(self):
        """Retrieve full path to the c++ compiler"""
        return self.cxx_path

    def get_cc_path(self):
        """Retrieve full path to the c compiler"""
        return self.cc_path

    def get_name(self):
        """Retrieve the full name of this compiler"""
        return f"{self.type}-{self.version}"

    def append_cxxflag(self, val, env=None):
        """Append a value to the cxxflags environment var"""
        env = env or self.comp_env
        flags = env.get("CXXFLAGS", "")
        env["CXXFLAGS"] = f"{flags} {val}"

    def append_cflag(self, val, env=None):
        """Append a value to the cflags environment var"""
        env = env or self.comp_env
        flags = env.get("CFLAGS", "")
        env["CFLAGS"] = f"{flags} {val}"

    def append_ldflag(self, val, env=None):
        """Append a value to the ldflags environment var"""
        env = env or self.comp_env
        flags = env.get("LDFLAGS", "")
        env["LDFLAGS"] = f"{flags} {val}"

    def append_compileflag(self, val, env=None):
        """Append a value to both the cxxflags and cflags"""
        self.append_cxxflag(val, env)
        self.append_cflag(val, env)

    def append_linkflag(self, val, env=None):
        """Append a value to both the ldflags"""
        self.append_ldflag(val, env)

    def init_compiler_env(self):
        """Initialize the compiler specific environment."""
        assert self.comp_env is None, "Compiler environment already initialized."

        if self.is_msvc():
            # Get a copy of the original ENV:
            logger.info("Initializing MSVC compiler environment...")
            orig_env = os.environ.copy()

            # We should keep only a very minimal PATH here:
            drive = os.getenv("HOMEDRIVE")
            assert drive is not None, "Invalid HOMEDRIVE variable."
            orig_env["PATH"] = f"{drive}\\Windows\\System32;{drive}\\Windows"

            # remove everything from our path:
            # del orig_env['PATH']

            cmd = [self.desc["setup_path"], "amd64"]
            result_env = get_environment_from_batch_command(cmd, orig_env)
            # logger.info("Collected updated MSVC environemt: %s", result_env)

            # Now we check what are the updated keys in that environment:
            self.comp_env = {}
            for key, value in result_env.items():
                if key not in orig_env:
                    self.comp_env[key] = value
                elif orig_env[key] != value:
                    logger.debug("Updating variable %s: %s -> %s", key, orig_env[key], value)
                    self.comp_env[key] = value

            # Add Windows\System32 and Windows to the path

            # logger.info("MSVC compiler environemt: %s", self.pretty_print(self.comp_env))

        if self.is_emcc():
            env = {}

            if self.is_windows:
                drive = os.getenv("HOMEDRIVE")
                assert drive is not None, "Invalid HOMEDRIVE variable."
                env["PATH"] = f"{self.get_cxx_dir()};{drive}\\Windows\\System32;{drive}\\Windows"
            else:
                env["PATH"] = self.get_cxx_dir()

            node_path = self.desc["node_path"]
            python_path = self.desc["python_path"]
            emsdk_dir = self.desc["emsdk_dir"]
            python_dir = self.get_parent_folder(python_path)

            node_dir = self.get_parent_folder(node_path)
            self.prepend_env_list([node_dir, emsdk_dir, python_dir], env, "PATH")
            env["EMSDK"] = emsdk_dir
            env["EMSDK_NODE"] = node_path
            env["EMSDK_PYTHON"] = python_path
            if self.is_windows:
                env["JAVA_HOME"] = self.desc["jre_dir"]
            env["EMSDK_PY"] = ""

            # SET PATH=D:\Projects\NervProj\tools\windows\emsdk-git;D:\Projects\NervProj\tools\windows\emsdk-git\upstream\emscripten;D:\Projects\NervProj\tools\windows\emsdk-git\node\15.14.0_64bit\bin;D:\Projects\NervProj;C:\Windows\system32;C:\Windows;
            # SET EMSDK=D:/Projects/NervProj/tools/windows/emsdk-git
            # SET EMSDK_NODE=D:\Projects\NervProj\tools\windows\emsdk-git\node\15.14.0_64bit\bin\node.exe
            # SET EMSDK_PYTHON=D:\Projects\NervProj\tools\windows\emsdk-git\python\3.9.2-nuget_64bit\python.exe
            # SET JAVA_HOME=D:\Projects\NervProj\tools\windows\emsdk-git\java\8.152_64bit
            # set EMSDK_PY=

            logger.info("C++ path: %s", self.get_cxx_path())
            # env["CC"] = self.get_cc_path()
            # env["CXX"] = self.get_cxx_path()

            # env["LD_LIBRARY_PATH"] = f"{self.libs_path}"
            self.comp_env = env

        if self.is_clang():
            env = {}

            if self.is_windows:
                drive = os.getenv("HOMEDRIVE")
                assert drive is not None, "Invalid HOMEDRIVE variable."
                env["PATH"] = f"{self.get_cxx_dir()};{drive}\\Windows\\System32;{drive}\\Windows"
            else:
                env["PATH"] = self.get_cxx_dir()

            env["CC"] = self.get_cc_path()
            env["CXX"] = self.get_cxx_path()

            # Do not use fPIC on windows:
            # fpic = " -fPIC" if self.is_linux else ""
            # env['CXXFLAGS'] = f"-I{inc_dir} {self.cxxflags}{fpic}"
            # env['CFLAGS'] = f"-I{inc_dir} -w{fpic}"

            env["LD_LIBRARY_PATH"] = f"{self.libs_path}"

            # If we are on windows, we also need the library path from the MSVC compiler:
            if self.is_windows:
                bman = self.ctx.get_component("builder")
                msvc_comp = bman.get_compiler("msvc")
                msvc_env = msvc_comp.get_env()

                logger.debug("MSVC compiler env: %s", self.pretty_print(msvc_env))
                env = self.prepend_env_list(msvc_env["LIB"], env, "LIB")
                env = self.prepend_env_list(msvc_env["INCLUDE"], env, "INCLUDE")
                env["UCRTVersion"] = msvc_env["UCRTVersion"]
                env["WindowsSDKLibVersion"] = msvc_env["WindowsSDKLibVersion"]
                env["WindowsSDKVersion"] = msvc_env["WindowsSDKVersion"]
                env["WindowsSdkBinPath"] = msvc_env["WindowsSdkBinPath"]
                env["WindowsSdkDir"] = msvc_env["WindowsSdkDir"]
                env["WindowsSdkVerBinPath"] = msvc_env["WindowsSdkVerBinPath"]
                env["VSINSTALLDIR"] = msvc_env["VSINSTALLDIR"]
                env["PATH"] = f"{self.get_cxx_dir()};{msvc_env['PATH']}"

                # env = self.prepend_env_list(msvc_env["WindowsLibPath"], env, "WindowsLibPath")
                # msvc_env = self.prepend_env_list([self.get_cxx_dir()], env)
                # msvc_env["CC"] = self.get_cc_path()
                # msvc_env["CXX"] = self.get_cxx_path()

            # else:
            # Add the include paths:
            # self.append_compileflag(f"-I{self.root_dir}/include/c++/v1", env)
            # self.append_compileflag(f"-I{self.root_dir}/lib/clang/{self.version}/include", env)
            # self.append_compileflag(f"-I{self.root_dir}/lib/clang/{self.version}/include/openmp_wrappers", env)

            # logger.info("clang compiler env: %s", env)
            self.comp_env = env

        assert self.comp_env is not None, "Cannot init compiler environment"

    def get_env(self, env=None):
        """Setup an environment using the current compiler config."""

        if env is None:
            env = os.environ.copy()
            # We don't want to keep any default PATH:
            if self.is_windows:
                del env["PATH"]
            if self.is_linux:
                # use a minimal path:
                env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

        if self.comp_env is None:
            self.init_compiler_env()

        # keep the previous PATH elements:
        prev_path = env.get("PATH", None)

        # update the env:
        env.update(self.comp_env)

        if prev_path is not None:
            env = self.append_env_list(prev_path, env)
            # sep = ";" if self.is_windows else ":"
            # env['PATH'] = env['PATH'] + sep + prev_path

        return env

    def get_init_script(self):
        """Retrieve the init script for this compiler if any"""
        if self.is_windows:
            return f"call {self.desc['setup_path']} amd64\n"

        return ""
