"""This module provide the builder for the LuaJIT library."""

import logging

from nvp.components.build import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder('LuaJIT', LuaJITBuilder(bman))


class LuaJITBuilder(NVPBuilder):
    """LuaJIT builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for LuaJIT on windows"""

        assert self.compiler.is_msvc(), "Only MSVC compiler is support on windows for LuaJIT compilation."

        # First we build the static library, and we install it,
        # and then we will build the shader library and install it
        # because otherwise we get a conflict on the shader/static library name.
        self.make_folder(prefix, "bin")
        self.make_folder(prefix, "include", "luajit")
        self.make_folder(prefix, "lib")

        # replace the /MD flag with /MT:
        self.replace_in_file(build_dir+"/src/msvcbuild.bat", "%LJCOMPILE% /MD /DLUA_BUILD_AS_DLL",
                             "%LJCOMPILE% /MT /DLUA_BUILD_AS_DLL")

        # # We write the temp.bat file:
        # build_file = build_dir+"/src/build.bat"
        # with open(build_file, 'w', encoding="utf-8") as bfile:
        #     bfile.write(comp.get_init_script())
        #     bfile.write(" static\n")

        # cmd = [build_file]

        logger.debug("Building LuaJIT static version...")
        build_file = self.get_path(build_dir, "src", "msvcbuild.bat")
        # assert self.file_exists(), "Invalid msvcbuild.bat file"
        # self.add_execute_permission(self.get_path(build_dir, "src", "msvcbuild.bat"))

        self.execute([build_file, "static"], cwd=build_dir+"/src", env=self.env)

        # install the static library:
        self.copy_file(build_dir+"/src/lua51.lib", prefix+"/lib/lua51_s.lib")
        self.copy_file(build_dir+"/src/luajit.exe", prefix+"/bin/luajit.exe")

        # Now we build the shared library:
        # with open(build_file, 'w', encoding="utf-8") as bfile:
        #     bfile.write(comp.get_init_script())
        #     bfile.write("msvcbuild.bat amalg\n")

        # cmd = [build_file]

        logger.debug("Building LuaJIT shared version...")
        # self.execute(cmd, cwd=build_dir+"/src")
        self.execute([build_file, "amalg"], cwd=build_dir+"/src", env=self.env)

        # Perform the installation manually:
        self.copy_file(build_dir+"/src/lua51.dll", prefix+"/bin/lua51.dll")
        self.copy_file(build_dir+"/src/lua51.lib", prefix+"/lib/lua51.lib")
        self.copy_file(build_dir+"/src/lauxlib.h", prefix+"/include/luajit/lauxlib.h")
        self.copy_file(build_dir+"/src/lua.h", prefix+"/include/luajit/lua.h")
        self.copy_file(build_dir+"/src/lua.hpp", prefix+"/include/luajit/lua.hpp")
        self.copy_file(build_dir+"/src/luaconf.h", prefix+"/include/luajit/luaconf.h")
        self.copy_file(build_dir+"/src/luajit.h", prefix+"/include/luajit/luajit.h")
        self.copy_file(build_dir+"/src/lualib.h", prefix+"/include/luajit/lualib.h")

    def build_on_linux(self, build_dir, prefix, desc):
        """Build method for LuaJIT on linux"""

        assert self.compiler.is_clang(), "Only clang compiler is support on linux for LuaJIT compilation."

        # End finally make install:
        self.execute(["make", "install", f"PREFIX={prefix}", "HOST_CC=clang"], cwd=build_dir, env=self.env)

        # We should rename the include sub folder: "luajit-2.1" -> "luajit"
        dst_name = self.get_path(prefix, "include", "luajit")
        self.rename_folder(f"{dst_name}-{desc['version']}", dst_name)
