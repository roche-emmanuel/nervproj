"""This module provide the builder for the sqlite library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("sqlite", Builder(bman))


class Builder(NVPBuilder):
    """sqlite builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        # cf. https://www.sqlite.org/howtocompile.html

        # Retrieve the def file:
        filename = "sqlite3.def"
        pkg_urls = self.ctx.get_config().get("package_urls", [])
        pkg_urls = [base_url + "libraries/" + filename for base_url in pkg_urls]

        pkg_url = self.ctx.select_first_valid_path(pkg_urls)
        self.check(pkg_url is not None, "Cannot find sqlite3 def file location for %s", filename)
        self.tools.download_file(pkg_url, self.get_path(build_dir, filename))

        cxx = self.compiler.get_cxx_path()

        flags = [
            "-O2",
            "-DSQLITE_ENABLE_FTS4",
            "-DSQLITE_ENABLE_FTS5",
            "-DSQLITE_ENABLE_RTREE",
            "-DSQLITE_ENABLE_DBSTAT_VTAB",
            "-DSQLITE_ENABLE_MATH_FUNCTIONS",
            "-DSQLITE_ENABLE_EXPLAIN_COMMENTS",
        ]
        # flags = ["-O2", "-DSQLITE_ENABLE_FTS4", "-DSQLITE_ENABLE_RTREE"]
        # flags = ["-O2"]
        # flags = []

        inc_dirs = self.env["INCLUDE"].split(";")
        # logger.info("Should use include folders %s", self.env["INCLUDE"])
        includes = [f"/I{idir}" for idir in inc_dirs]
        lib_dirs = self.env["LIB"].split(";")

        libs = [f"/LIBPATH:{ldir}" for ldir in lib_dirs]

        # Build the library:
        # cl sqlite3.c -link -dll -out:sqlite3.dll
        cmd = (
            [
                cxx,
                "sqlite3.c",
                "-DSQLITE_API=__declspec(dllexport)",
            ]
            + includes
            + flags
            + ["-link", "-dll", "-out:sqlite3.dll", "/IMPLIB:sqlite3.lib"]
            + libs
        )
        self.execute(cmd, cwd=build_dir)

        # Generate the lib:
        # dumpbin /exports DLL_FILE.dll > DEF_FILE.def
        # cxx_dir = self.compiler.get_cxx_dir()
        # cmd = [self.get_path(cxx_dir, "dumpbin.exe"), "/exports", "sqlite3.dll"]
        # deffile = open(self.get_path(build_dir, filename), "w", encoding="utf-8")
        # self.execute(cmd, cwd=build_dir, outfile=deffile)
        # deffile.close()

        # lib /def:DEF_FILE.def /out:LIB_FILE.lib /machine:x86
        # cmd = [self.get_path(cxx_dir, "lib.exe"), "/def:sqlite3.def", "/out:sqlite3.lib", "/machine:x64"]
        # cmd = [self.get_path(cxx_dir, "lib.exe"), "/def:sqlite3.def", "/out:sqlite3.lib", "/machine:x86"]
        # self.execute(cmd, cwd=build_dir)

        # Build the executable:
        # cl shell.c sqlite3.c -Fesqlite3.exe
        cmd = [cxx, "sqlite3.c", "shell.c", "-Fesqlite3.exe"] + includes + flags + ["/link"] + libs
        self.execute(cmd, cwd=build_dir)

        if not self.file_exists(self.get_path(build_dir, "sqlite3.exe")):
            self.throw("Compilation failed.")

        # Install the files:
        self.make_folder(self.get_path(prefix, "include"))
        self.make_folder(self.get_path(prefix, "lib"))
        self.make_folder(self.get_path(prefix, "bin"))
        self.copy_file(self.get_path(build_dir, "sqlite3.h"), self.get_path(prefix, "include", "sqlite3.h"))
        self.copy_file(self.get_path(build_dir, "sqlite3ext.h"), self.get_path(prefix, "include", "sqlite3ext.h"))
        self.copy_file(self.get_path(build_dir, "sqlite3.lib"), self.get_path(prefix, "lib", "sqlite3.lib"))
        self.copy_file(self.get_path(build_dir, "sqlite3.exe"), self.get_path(prefix, "bin", "sqlite3.exe"))
        self.copy_file(self.get_path(build_dir, "sqlite3.dll"), self.get_path(prefix, "bin", "sqlite3.dll"))

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        # gcc shell.c sqlite3.c -lpthread -ldl -lm -o sqlite3
        # flags = []
        # self.run_cmake(build_dir, prefix, ".", flags=flags)
        # self.run_ninja(build_dir)

        # cf. https://stackoverflow.com/questions/36471765/building-sqlite-dll-with-vs2015


#         """if(BUILD_SHARED_LIBS)
#     if(WIN32)
#         target_compile_definitions(${PROJECT_NAME}
#            PRIVATE
#                "SQLITE_API=__declspec(dllexport)"
#         )
#     else() # haven't tested that
#         target_compile_definitions(${PROJECT_NAME}
#            PRIVATE
#                "SQLITE_API=__attribute__((visibility(\"default\")))"
#         )
#     endif()
# endif()"""
