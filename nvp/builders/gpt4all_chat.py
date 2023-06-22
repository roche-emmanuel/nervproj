"""This module provide the builder for the gpt4all_chat library."""

import logging

from nvp.core.build_manager import BuildManager
from nvp.nvp_builder import NVPBuilder

logger = logging.getLogger(__name__)


def register_builder(bman: BuildManager):
    """Register the build function"""

    bman.register_builder("gpt4all_chat", Builder(bman))


class Builder(NVPBuilder):
    """gpt4all_chat builder class."""

    def build_on_windows(self, build_dir, prefix, _desc):
        """Build on windows method"""

        # Note: the final app is nto working for now,
        # might need to explicitly build with QT 6.5 ?

        qt_dir = self.man.get_library_root_dir("QT6")
        deploy = self.get_path(qt_dir, "bin", "windeployqt.exe")

        qt_dir = self.get_path(qt_dir, "lib", "cmake", "Qt6")
        logger.info("Using qt6 dir: %s", qt_dir)

        flags = ["-S", "gpt4all-chat", "-B", "release_build", f"-DQt6_DIR={qt_dir}"]

        self.patch_file(
            self.get_path(build_dir, "gpt4all-chat", "CMakeLists.txt"),
            "find_package(Qt6 6.5 COMPONENTS",
            "find_package(Qt6 6.4 COMPONENTS",
        )
        self.patch_file(
            self.get_path(build_dir, "gpt4all-chat", "chatllm.cpp"),
            "Qt_6_5",
            "Qt_6_4",
        )
        self.patch_file(
            self.get_path(build_dir, "gpt4all-chat", "chatgpt.cpp"),
            'qWarning() << QString("ERROR: ChatGPT',
            '//qWarning() << QString("ERROR: ChatGPT',
        )
        self.patch_file(
            self.get_path(build_dir, "gpt4all-chat", "chatgpt.cpp"),
            ".arg(code).arg(reply->errorString()).toStdString();",
            '//.arg(code).arg(reply->errorString()).toStdString();\nqWarning() << "ERROR: ChatGPT responded with error code " << code << "-" << reply->errorString();',
        )
        self.patch_file(
            self.get_path(build_dir, "gpt4all-chat", "qml", "AboutDialog.qml"),
            "abpoutDialog",
            "aboutDialog",
        )
        self.patch_file(
            self.get_path(build_dir, "gpt4all-chat", "qml", "SettingsDialog.qml"),
            "Settings {",
            "MySettings {",
        )

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        sub_dir = self.get_path(build_dir, "release_build")
        self.run_ninja(sub_dir)

        # Move the install folder:
        self.move_path(self.get_path(sub_dir, "install"), prefix)

        # install deps with windeployqt:
        bin_dir = self.get_path(prefix, "bin")
        qml_dir = self.get_path(sub_dir, "gpt4all")

        cmd = [deploy, "--qmldir", qml_dir, "--release", "chat.exe"]
        res, rcode, outs = self.execute(cmd, cwd=bin_dir, env=self.env)

        if not res:
            logger.error("windeploy command %s (in %s) failed with return code %d:\n%s", cmd, bin_dir, rcode, outs)
            self.throw("Detected build failure.")

    def build_on_linux(self, build_dir, prefix, desc):
        """Build on linux method"""
        flags = ["-DSSE=ON", "-DSTATIC=ON"]
        # if self.compiler.is_emcc():
        #     flags = ["-DBUILD_SHARED_LIBS=OFF"]

        self.run_cmake(build_dir, prefix, ".", flags=flags)
        self.run_ninja(build_dir)
