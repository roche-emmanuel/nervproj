"""This module provide the builder for the ggml library."""

import logging
import re

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("ggml", Builder(bman))


class Builder(NVPBuilder):
    """ggml builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""
        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

        # logger.info("Installing dawn libraries...")
        def install_files(src_folder, exp, dst_folder, hint, **kwargs):
            # Get all the dawn libs:
            base_dir = kwargs.get("src_dir", sub_dir)
            flatten = kwargs.get("flatten", True)
            excluded = kwargs.get("excluded", [])
            src_dir = self.get_path(base_dir, src_folder)
            all_files = self.get_all_files(src_dir, exp=exp, recursive=True)

            dst_dir = self.get_path(prefix, dst_folder)
            self.make_folder(dst_dir)

            res = []

            # copy the dawn libraries:
            for elem in all_files:
                ignored = False
                for pat in excluded:
                    if re.search(pat, elem) is not None:
                        ignored = True
                        break

                if ignored:
                    logger.info("Ignoring element %s", elem)
                    continue

                logger.info("Installing %s %s", hint, elem)
                src = self.get_path(src_dir, elem)
                dst_file = self.get_filename(src) if flatten else elem
                dst = self.get_path(dst_dir, dst_file)
                pdir = self.get_parent_folder(dst)
                self.make_folder(pdir)

                self.check(not self.file_exists(dst), "File %s already exists.", dst)
                self.copy_file(src, dst)
                res.append(elem)

            return res

        install_files("include/ggml", r"\.h$", "include/ggml", "header")
        install_files("bin", r"\.exe$", "bin", "apps")

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        flags = ["-S", ".", "-B", "release_build", "-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)
