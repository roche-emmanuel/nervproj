"""Main module for the SDLab application"""

import logging
import os

import PyQt5.QtWidgets as qwd
from PyQt5 import QtCore

from nvp.gui.app_base import AppBase
from nvp.gui.utils import NVPGui as gui
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class SDLab(AppBase):
    """SDLab component class"""

    def __init__(self, ctx: NVPContext):
        """class constructor"""
        AppBase.__init__(self, ctx, "SDLab")
        self.config.setdefault("application_title", "SDLab")

        # Load the local config file:
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        cur_dir = self.to_absolute_path(cur_dir)

        self.app_dir = self.get_parent_folder(cur_dir, level=1)
        logger.info("SDLab root app dir: %s", self.app_dir)

        cfg_file = self.get_path(cur_dir, "config.yml")
        logger.info("Loading config file: %s", cfg_file)
        cfg = self.read_yaml(cfg_file)

        # Use the global config to update this default local config:
        if cfg is None:
            cfg = self.config
        else:
            cfg.update(self.config)

        # Then store that as config:
        self.config = cfg
        logger.info("SDLab config: %s", self.config)

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "run":
            self.run_app()
            return True

        return False

    def build_app(self):
        """Re-implementation of the build function"""
        super().build_app()

        self.empty_icon = gui.create_empty_icon()
        self.check_icon = gui.create_icon("tick")

        win = self.get_main_window()

        win.setWindowIcon(gui.create_icon("sdlab_icon"))

        self.build_menu()

        # Extend the status bar:
        self.sb_index_lbl = qwd.QLabel()
        status_bar = win.statusBar()
        status_bar.addPermanentWidget(self.sb_index_lbl)

        # Set a size hint on the window:
        width = self.config.get("window_width", 1600)
        height = self.config.get("window_height", 1200)

        setattr(win, "sizeHint", lambda: QtCore.QSize(width, height))

    def build_menu(self):
        """Build the menu bar"""

        win = self.get_main_window()

        mbar = win.menuBar()

        menu = mbar.addMenu("&File")
        act = qwd.QAction(gui.create_icon("folder-open-document"), "Open folder...", win)
        # act.triggered.connect(self.open_folder)
        menu.addAction(act)

        act = qwd.QAction(gui.create_icon("control-power"), "Exit", win)
        act.setShortcut("Ctrl+Q")
        act.triggered.connect(win.close)
        menu.addAction(act)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our components:
    comp = context.register_component("app", SDLab(context))

    psr = context.build_parser("run")
    # We may provide a path from where to start the app:

    # psr.add_str("input", nargs="?", default=None)("Input directory to load content from.")
    # psr.add_str("-t", "--tags")("List of tags to use for filtering, should be separated by '/'")
    # psr.add_int("-s", "--start", dest="start_index")("Start index for display")

    comp.run()
