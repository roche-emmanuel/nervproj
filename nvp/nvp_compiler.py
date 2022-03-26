"""This module contains a definition of a compiler class for NVP"""
import logging
import os

from nvp.nvp_object import NVPObject

logger = logging.getLogger(__name__)


class NVPCompiler(NVPObject):
    """A class representing a compiler"""

    def __init__(self, desc):
        """Compiler class constructor"""
        assert 'type' in desc, "Invalid compiler type"
        self.desc = desc
        self.type = desc['type']
        self.cxxflags = None
        self.linkflags = None
        self.libs_path = None
        self.version = None
        self.version_major = None
        self.version_minor = None
        self.cxx_path = None
        self.cc_path = None

        ext = ".exe" if self.is_windows else ""

        if self.type == 'msvc':
            # This compiler must always be available:
            setup_file = desc['setup_path']
            assert self.file_exists(setup_file), f"Invalid MSVC setup path: {setup_file}"
            # setup is: VC/Auxiliary/Build/vcvarsall.bat
            self.root_dir = self.get_parent_folder(setup_file)  # Build dir
            self.root_dir = self.get_parent_folder(self.root_dir)  # Aux dir
            self.root_dir = self.get_parent_folder(self.root_dir)  # VC dir
            self.root_dir = self.get_parent_folder(self.root_dir)  # root dir
            logger.info("MSVC root dir is: %s", self.root_dir)

        else:
            assert self.type == 'clang', f"No support for compiler type {self.type}"
            self.root_dir = desc['root_dir']

            self.cxx_path = self.get_path(self.root_dir, "bin", "clang++"+ext)
            self.cc_path = self.get_path(self.root_dir, "bin", "clang"+ext)
            self.libs_path = self.get_path(self.root_dir, "lib")

            # self.cxxflags = "-stdlib=libc++ -nodefaultlibs -lc++ -lc++abi -lm -lc -lgcc_s -lpthread"
            self.cxxflags = "-stdlib=libc++ -w"
            self.linkflags = "-stdlib=libc++ -nodefaultlibs -lc++ -lc++abi -lm -lc -lgcc_s -lpthread"

            # extract the version number from the root_dir:
            parts = self.root_dir.split('-')
            assert len(parts) >= 2, f"Invalid root dir format for compiler {self.root_dir}"
            self.version = parts[-1]
            parts = self.version.split(".")
            assert len(parts) >= 2, f"Invalid compiler version {self.version}"
            self.version_major = int(parts[0])
            self.version_minor = int(parts[1])

    def get_type(self):
        """Return this compiler type"""
        return self.desc['type']

    def is_msvc(self):
        """Check if this is an MSVC compiler"""
        return self.get_type() == "msvc"

    def is_clang(self):
        """Check if this is a clang compiler"""
        return self.get_type() == "clang"

    def is_available(self):
        """Check if this compiler is currently available."""
        if self.type == 'msvc':
            return True

        return self.file_exists(self.get_cxx_path())

    def get_weight(self, selected_type):
        """Retrive the weight of this compiler."""
        if not self.is_available():
            return 0

        # Compiler is available:
        weight = self.get_major_version()*100 + self.get_minor_version()
        if selected_type == self.type:
            weight += 1000000

        return weight

    def get_cxxflags(self):
        """Retrieve the cxxflags"""
        return self.cxxflags

    def get_linkflags(self):
        """Retrieve the linkflags"""
        return self.linkflags

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
        return self.get_path(self.root_dir, "bin")

    def get_cxx_path(self):
        """Retrieve full path to the c++ compiler"""
        return self.cxx_path

    def get_cc_path(self):
        """Retrieve full path to the c compiler"""
        return self.cc_path

    def get_env(self, env=None):
        """Setup an environment using the current compiler config."""

        if env is None:
            env = os.environ.copy()

        if self.is_msvc():
            return env

        env['PATH'] = self.get_cxx_dir()+":"+env['PATH']

        inc_dir = f"{self.root_dir}/include/c++/v1"

        env['CC'] = self.get_cc_path()
        env['CXX'] = self.get_cxx_path()
        env['CXXFLAGS'] = f"-I{inc_dir} {self.cxxflags} -fPIC"
        env['CFLAGS'] = f"-I{inc_dir} -w -fPIC"

        env['LD_LIBRARY_PATH'] = f"{self.libs_path}"

        return env

    def get_init_script(self):
        """Retrieve the init script for this compiler if any"""
        if self.is_windows:
            return f"call {self.desc['setup_path']} amd64\n"

        return ""
