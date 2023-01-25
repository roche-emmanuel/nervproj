"""Simple GUI utilities"""

import ctypes
import logging
import sys

import PyQt5.QtWidgets as qwd
from PyQt5 import QtCore, QtGui

from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class NVPGui(object):
    """Collection of GUI utility functions"""

    @staticmethod
    def create_empty_icon():
        """Create an empty icon"""
        return QtGui.QIcon("")

    @staticmethod
    def create_icon(name):
        """Create a new icon from an icon name"""
        ctx = NVPContext.get()
        app = ctx.get_component("app")
        fname = app.get_path(app.get_app_dir(), "assets", "icons", f"{name}.png")
        if not app.file_exists(fname):
            logger.error("Cannot find icon file %s", fname)

        return QtGui.QIcon(fname)

    @staticmethod
    def create_bitmap_button(iname, text="", size=16):
        """Create a bitmap button from a given icon name"""
        btn = qwd.QPushButton(text)
        btn.setIcon(NVPGui.create_icon(iname))
        btn.setIconSize(QtCore.QSize(size, size))
        return btn

    @staticmethod
    def get_display_scale_factor():
        """Retrieve the scale factor in use for the display"""
        # cf. https://stackoverflow.com/questions/53889520/getting-screen-pixels-taking-into-account-the-scale-factor
        if sys.platform.startswith("win32"):
            return ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100

        # By default, we just return 1:
        return 1.0
