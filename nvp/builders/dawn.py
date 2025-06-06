"""This module provide the builder for the dawn library."""

import logging

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
        git_dir = self.tools.get_tool_dir("git")
        ninja_dir = self.tools.get_tool_dir("ninja")
        self.env["PATH"] = git_dir + ";" + ninja_dir + ";" + self.env["PATH"]
        # python_dir = self.tools.get_tool_dir("python")
        # self.env["PATH"] = python_dir + ";" + ninja_dir + ";" + self.env["PATH"]

        # Need the following define on windows to avoid an issue:
        # cf. https://chromium.googlesource.com/chromium/src/+/HEAD/docs/windows_build_instructions.md
        self.env["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"

        # Need to patch gclient bootstrap.py below:
        gclient_dir = self.tools.get_tool_dir("gclient")
        bootstrap_file = self.get_path(gclient_dir, "bootstrap", "bootstrap.py")
        self.patch_file(bootstrap_file, "if tail.lower() == 'git':", "if tail.lower().startswith('git'):")

        # Patch for v20250417 compilation
        tint_vector_file = self.get_path(build_dir, "src/tint/utils/containers/vector.h")
        self.patch_file(
            tint_vector_file,
            "void Grow() { Reserve(std::max(impl_.slice.cap, static_cast<size_t>(1)) * 2); }",
            "void Grow() { Reserve((impl_.slice.cap>1?impl_.slice.cap:1) * 2); }",
        )

        # Fetch external dependencies and toolchains with gclient
        # gclient sync
        # write a custom script here to call gclient with the git path available:
        # content = f"set PATH={git_dir};%PATH%\n"
        # content += f"{gclient_path} sync\n"
        # gclient_alt = self.get_path(build_dir, "gclient_sync.bat")
        # self.write_text_file(content, gclient_alt)

        cmd = [gclient_path, "sync"]
        # cmd = [gclient_alt]
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
            f"-DPython3_EXECUTABLE={py_path}",
            "-DDAWN_ENABLE_PIC=ON",
            # "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)

        logger.info("Executing ninja...")
        sub_dir = self.get_path(build_dir, "release_build")
        # self.run_ninja(sub_dir)
        self.exec_ninja(sub_dir)

        # logger.info("Installing dawn libraries...")

        self.set_install_context(sub_dir, prefix)

        self.install_files("src/dawn", r"\.lib$", "lib", "library", recurse=True)
        self.install_files("src/tint", r"\.lib$", "lib", "library", recurse=True)
        absl_libs = self.install_files("third_party", r"absl_.*\.lib$", "lib", "library", recurse=True)
        self.install_files("third_party", r"SPIRV-Tools.*\.lib$", "lib", "library", recurse=True)
        self.install_files("gen/include", r"\.h$", "include", "header", flatten=False, recurse=True)
        self.install_files("include", r"\.h$", "include", "header", src_dir=build_dir, flatten=False, recurse=True)
        self.install_files(
            "src/dawn", r"\.h$", "include/internals/dawn", "dawn_header", src_dir=build_dir, flatten=False, recurse=True
        )
        self.install_files(
            "src/tint", r"\.h$", "include/internals/tint", "tint_header", src_dir=build_dir, flatten=False, recurse=True
        )
        self.install_files(".", r"\.exe$", "bin", "app", excluded=["CMake", "unittests"], recurse=True)

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
            f"-DPython3_EXECUTABLE={py_path}",
            "-DDAWN_ENABLE_PIC=ON",
            # "-DBUILD_SHARED_LIBS=OFF",
        ]

        self.run_cmake(build_dir, prefix, flags=flags)

        logger.info("Executing ninja...")
        sub_dir = self.get_path(build_dir, "release_build")
        # self.run_ninja(sub_dir)
        self.exec_ninja(sub_dir)

        self.set_install_context(sub_dir, prefix)

        self.install_files("src/dawn", r"\.a$", "lib", "library", recurse=True)
        self.install_files("src/tint", r"\.a$", "lib", "library", recurse=True)
        absl_libs = self.install_files("third_party", r"absl_.*\.a$", "lib", "library", recurse=True)
        self.install_files("third_party", r"SPIRV-Tools.*\.a$", "lib", "library", recurse=True)
        self.install_files("gen/include/dawn", r"\.h$", "include/dawn", "header", flatten=False, recurse=True)
        self.install_files("include", r"\.h$", "include", "header", src_dir=build_dir, flatten=False, recurse=True)
        self.install_files(".", "tint$", "bin", "app", recurse=True)
        self.install_files(".", "tint_info$", "bin", "app", recurse=True)
        self.install_files(".", "tint-loopy$", "bin", "app", recurse=True)
        self.install_files(".", "HelloTriangle$", "bin", "app", recurse=True)
        self.install_files(".", "meter$", "bin", "app", recurse=True)
        self.install_files(".", "Boids$", "bin", "app", recurse=True)
        self.install_files(
            "src/dawn", r"\.h$", "include/internals/dawn", "dawn_header", src_dir=build_dir, flatten=False, recurse=True
        )
        self.install_files(
            "src/tint", r"\.h$", "include/internals/tint", "tint_header", src_dir=build_dir, flatten=False, recurse=True
        )

        # Write the list of absl libs to file:
        absl_libs = [self.get_filename(elem) for elem in absl_libs]
        self.write_text_file("\n".join(absl_libs), self.get_path(prefix, "lib", "absl_libs.txt"))

        logger.info("Dawn build done.")
