"""This module provide the builder for the cairo library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("cairo", Builder(bman))


class Builder(NVPBuilder):
    """cairo builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Only applicable to msvc
        self.check(self.compiler.is_msvc(), "Only available with MSVC compiler")

        # Reference:
        # cd cairo
        # sed 's/-MD/-MT/;s/zdll.lib/zlib.lib/' build/Makefile.win32.common > Makefile.win32.common.fixed
        # mv Makefile.win32.common.fixed build/Makefile.win32.common
        # if [ $USE_FREETYPE -ne 0 ]; then
        #     sed '/^CAIRO_LIBS =/s/$/ $(top_builddir)\/..\/freetype\/freetype.lib/;/^DEFAULT_CFLAGS =/s/$/ -I$(top_srcdir)\/..\/freetype\/include/' build/Makefile.win32.common > Makefile.win32.common.fixed
        # else
        #     sed '/^CAIRO_LIBS =/s/ $(top_builddir)\/..\/freetype\/freetype.lib//;/^DEFAULT_CFLAGS =/s/ -I$(top_srcdir)\/..\/freetype\/include//' build/Makefile.win32.common > Makefile.win32.common.fixed
        # fi
        # mv Makefile.win32.common.fixed build/Makefile.win32.common
        # sed "s/CAIRO_HAS_FT_FONT=./CAIRO_HAS_FT_FONT=$USE_FREETYPE/" build/Makefile.win32.features > Makefile.win32.features.fixed
        # mv Makefile.win32.features.fixed build/Makefile.win32.features
        # # pass -B for switching between x86/x64
        # make -B -f Makefile.win32 cairo "CFG=release"
        # cd ..

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        pixman_dir = self.man.get_library_root_dir("pixman").replace("\\", "/")
        ft_dir = self.man.get_library_root_dir("freetype").replace("\\", "/")
        brotli_dir = self.man.get_library_root_dir("brotli").replace("\\", "/")
        harfbuzz_dir = self.man.get_library_root_dir("harfbuzz").replace("\\", "/")

        # brotli_lib = "brotlidec.a" if self.compiler.is_emcc() else "brotlidec.lib"
        # harfbuzz_lib = "harfbuzz.a" if self.compiler.is_emcc() else "harfbuzz.lib"
        # png_lib = "libpng16_static.lib" if self.is_windows else "libpng16.a"
        # z_lib = "zlibstatic.lib" if self.is_windows else "libz.a"

        # Path the Makefile.win32.common file:
        ft_libs = f"{ft_dir}/lib/freetype.lib {harfbuzz_dir}/lib/harfbuzz.lib"
        ft_libs += f" {brotli_dir}/lib/brotlidec.lib {brotli_dir}/lib/brotlicommon.lib"

        self.multi_patch_file(
            self.get_path(build_dir, "build/Makefile.win32.common"),
            # ("-MD", "-MT"),
            ("-I$(ZLIB_PATH)/", f"-I{zlib_dir}/include -I{ft_dir}/include/freetype2"),
            ("$(ZLIB_PATH)/zdll.lib", f"{zlib_dir}/lib/zlibstatic.lib {ft_libs}"),
            ("-I$(LIBPNG_PATH)/", f"-I{png_dir}/include"),
            ("$(LIBPNG_PATH)/libpng.lib", f"{png_dir}/lib/libpng16_static.lib"),
            ("-I$(PIXMAN_PATH)/pixman/", f"-I{pixman_dir}/include"),
            ("$(PIXMAN_PATH)/pixman/$(CFG)/pixman-1.lib", f"{pixman_dir}/lib/pixman-1.lib"),
            ("@mkdir -p $(CFG)/`dirname $<`", ""),
            # ("CFG_LDFLAGS :=", "CFG_LDFLAGS := "),
        )
        #  /NODEFAULTLIB:MSVCRT /NODEFAULTLIB:libucrt
        self.patch_file(
            self.get_path(build_dir, "build/Makefile.win32.features"), "CAIRO_HAS_FT_FONT=0", "CAIRO_HAS_FT_FONT=1"
        )
        self.patch_file(self.get_path(build_dir, "build/Makefile.win32.features-h"), '"', "")
        self.patch_file(
            self.get_path(build_dir, "src/Makefile.win32"),
            '@for x in $(enabled_cairo_headers); do echo "	src/$$x"; done',
            "",
        )

        # Manually prepare the build folders:
        self.make_folder(self.get_path(build_dir, "src/release/win32"))

        # Run the make command:
        flags = ["-B", "-f", "Makefile.win32", "cairo", "CFG=release"]
        self.exec_make(build_dir, flags)

        # Manually install the files:
        headers = [
            "cairo-features.h",
            "cairo.h",
            "cairo-deprecated.h",
            "cairo-win32.h",
            "cairo-script.h",
            "cairo-ps.h",
            "cairo-pdf.h",
            "cairo-svg.h",
            "cairo-ft.h",
        ]

        self.install_files(".", r"cairo-version\.h$", "include")
        self.install_files("src", r"\.h$", "include", included=headers)
        self.install_files("src/release", r"cairo\.dll$", "bin")
        self.install_files("src/release", r"cairo\.lib$", "lib")
        self.install_files("src/release", r"cairo-static\.lib$", "lib")

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""

        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF", "-DFT_REQUIRE_ZLIB=TRUE"]
        # if self.compiler.is_emcc():

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
