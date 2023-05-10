"""This module provide the builder for the dawn library."""

import logging
import re

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("dawn", DawnBuilder(bman))


class DawnBuilder(NVPBuilder):
    """dawn builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build method for dawn on windows"""

        # Discard any change to depot_tools:
        logger.info("Updating depot_tools...")
        depot_dir = self.tools.get_tool_dir("gclient")
        git = self.tools.get_component("git")

        git.git_checkout(depot_dir, discard=True)
        git.git_checkout(depot_dir, branch="main")
        git.git_pull(depot_dir)

        # Bootstrap the gclient configuration
        # cp scripts/standalone.gclient .gclient
        logger.info("Copying gclient config...")
        self.copy_file(self.get_path(build_dir, "scripts", "standalone.gclient"), self.get_path(build_dir, ".gclient"))

        gclient_path = self.tools.get_tool_path("gclient")

        # Should also add the depot_tools folder in the PATH:
        # Also add path to powershell:
        paths = [depot_dir, "C:\\Windows\\System32\\WindowsPowerShell\\v1.0"]
        self.prepend_env_list(paths, self.env)

        # Force adding ninja path on top:
        ninja_dir = self.tools.get_tool_dir("ninja")
        self.env["PATH"] = ninja_dir + ";" + self.env["PATH"]

        # Need the following define on windows to avoid an issue:
        # cf. https://chromium.googlesource.com/chromium/src/+/HEAD/docs/windows_build_instructions.md
        self.env["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"

        # Fetch external dependencies and toolchains with gclient
        # gclient sync
        cmd = [gclient_path, "sync"]
        logger.info("Executing gclient sync...")
        self.execute(cmd, cwd=build_dir, env=self.env)

        # Run cmake:
        logger.info("Executing cmake...")
        # Need to add python executable path:
        py_path = self.tools.get_tool_path("python")
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            f"-DPYTHON_EXECUTABLE={py_path}",
            f"-DPython_EXECUTABLE={py_path}",
            "-DDAWN_ENABLE_PIC=ON",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)

        logger.info("Executing ninja...")
        sub_dir = self.get_path(build_dir, "release_build")
        # self.run_ninja(sub_dir)
        self.exec_ninja(sub_dir)

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

        install_files("src/dawn", r"\.lib$", "lib", "library")
        install_files("src/tint", r"\.lib$", "lib", "library")
        absl_libs = install_files("third_party", r"absl_.*\.lib$", "lib", "library")
        install_files("third_party", r"SPIRV-Tools.*\.lib$", "lib", "library")
        install_files("gen/include/dawn", r"\.h$", "include/dawn", "header")
        install_files("include", r"\.h$", "include", "header", src_dir=build_dir, flatten=False)
        install_files(".", r"\.exe$", "bin", "app", excluded=["CMake", "unittests"])

        # Write the list of absl libs to file:
        absl_libs = [self.get_filename(elem) for elem in absl_libs]
        self.write_text_file("\n".join(absl_libs), self.get_path(prefix, "lib", "absl_libs.txt"))

        logger.info("Dawn build done.")

    def build_on_linux(self, build_dir, prefix, _desc):
        """Build method for dawn on linux"""

        # Need to install the following packages:
        # sudo apt-get install libxinerama-dev
        # Bootstrap the gclient configuration
        # cp scripts/standalone.gclient .gclient
        logger.info("Copying gclient config...")
        self.copy_file(self.get_path(build_dir, "scripts", "standalone.gclient"), self.get_path(build_dir, ".gclient"))

        gclient_path = self.tools.get_tool_path("gclient")

        # Should also add the depot_tools folder in the PATH:
        depot_dir = self.tools.get_tool_dir("gclient")
        paths = [depot_dir]
        self.prepend_env_list(paths, self.env)

        # Force adding ninja path on top:
        ninja_dir = self.tools.get_tool_dir("ninja")
        self.env["PATH"] = ninja_dir + ":" + self.env["PATH"]

        # Fetch external dependencies and toolchains with gclient
        # gclient sync
        cmd = [gclient_path, "sync"]
        logger.info("Executing gclient sync...")
        self.execute(cmd, cwd=build_dir, env=self.env)

        # Run cmake:
        logger.info("Executing cmake...")
        # Need to add python executable path:
        py_path = self.tools.get_tool_path("python")
        flags = [
            "-S",
            ".",
            "-B",
            "release_build",
            f"-DPYTHON_EXECUTABLE={py_path}",
            f"-DPython_EXECUTABLE={py_path}",
            "-DDAWN_ENABLE_PIC=ON",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)

        logger.info("Executing ninja...")
        sub_dir = self.get_path(build_dir, "release_build")
        # self.run_ninja(sub_dir)
        self.exec_ninja(sub_dir)

        res = []

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

        install_files("src/dawn", r"\.a$", "lib", "library")
        install_files("src/tint", r"\.a$", "lib", "library")
        absl_libs = install_files("third_party", r"absl_.*\.a$", "lib", "library")
        install_files("third_party", r"SPIRV-Tools.*\.a$", "lib", "library")
        install_files("gen/include/dawn", r"\.h$", "include/dawn", "header")
        install_files("include", r"\.h$", "include", "header", src_dir=build_dir, flatten=False)
        install_files(".", "tint$", "bin", "app")
        install_files(".", "tint_info$", "bin", "app")
        install_files(".", "tint-loopy$", "bin", "app")
        install_files(".", "HelloTriangle$", "bin", "app")
        install_files(".", "meter$", "bin", "app")
        install_files(".", "Boids$", "bin", "app")

        # Write the list of absl libs to file:
        absl_libs = [self.get_filename(elem) for elem in absl_libs]
        self.write_text_file("\n".join(absl_libs), self.get_path(prefix, "lib", "absl_libs.txt"))

        logger.info("Dawn build done.")
