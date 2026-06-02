"""This module provide the builder for the OSG library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("OSG", Builder(bman))


class Builder(NVPBuilder):
    """OSG builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        zlib_dir = self.man.get_library_root_dir("zlib").replace("\\", "/")
        z_lib = "libz.a" if self.compiler.is_emcc() else "zlibstatic.lib"
        png_dir = self.man.get_library_root_dir("libpng").replace("\\", "/")
        png_lib = "libpng16.a" if self.compiler.is_emcc() else "libpng16_static.lib"
        ft_dir = self.man.get_library_root_dir("freetype").replace("\\", "/")
        ft_lib = "freetype.lib"
        jpeg_dir = self.man.get_library_root_dir("libjpeg").replace("\\", "/")
        jpeg_lib = "jpeg-static.lib"
        xml_dir = self.man.get_library_root_dir("libxml2").replace("\\", "/")
        xml_lib = "libxml2s.lib"
        sdl2_dir = self.man.get_library_root_dir("SDL2").replace("\\", "/")
        sdl2_lib = "SDL2-static.lib"

        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DOPENGL_PROFILE=GL3",
            f"-DZLIB_LIBRARY={zlib_dir}/lib/{z_lib}",
            f"-DZLIB_INCLUDE_DIR={zlib_dir}/include",
            f"-DPNG_LIBRARY={png_dir}/lib/{png_lib}",
            f"-DPNG_PNG_INCLUDE_DIR={png_dir}/include",
            f"-DFREETYPE_LIBRARY={ft_dir}/lib/{ft_lib}",
            f"-DFREETYPE_INCLUDE_DIRS={ft_dir}/include/freetype2",
            f"-DJPEG_LIBRARY={jpeg_dir}/lib/{jpeg_lib}",
            f"-DJPEG_INCLUDE_DIR={jpeg_dir}/include",
            f"-DLIBXML2_LIBRARY={xml_dir}/lib/{xml_lib}",
            f"-DLIBXML2_INCLUDE_DIR={xml_dir}/include",
            f"-DSDL2_LIBRARY={sdl2_dir}/lib/{sdl2_lib}",
            f"-DSDL2_INCLUDE_DIR={sdl2_dir}/include",
            "-DCMAKE_CXX_FLAGS=/DWIN32 /D_WINDOWS /W4 /GR /EHsc",
            "-DCMAKE_C_FLAGS=/DWIN32 /D_WINDOWS /W3",
        ]

        self.patch_file(
            self.get_path(build_dir, "src/osgPlugins/osga/OSGA_Archive.cpp"),
            "_FPOSOFF",
            "(long long)",
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build on linux method"""
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            "-DOPENGL_PROFILE=GL3",
        ]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(self.get_path(build_dir, "release_build"))
