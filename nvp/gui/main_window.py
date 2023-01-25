"""Module for the main window of the application"""

import logging

# from PyQt5.QtCore import Qt
# from PyQt5 import QtCore
import PyQt5.QtWidgets as qwd

from nvp.core.event import NVPEvent
from nvp.gui.utils import NVPGui as gui
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class MainWindow(qwd.QMainWindow):
    """Main Window class for application"""

    def __init__(self, app):
        """Constructor of the MainWindow class"""
        super().__init__()

        self.app = app

        # Retrieve the app config:
        self.config = app.get_config()

        # keep ref on the context:
        self.ctx = NVPContext.get()

        title = self.config["application_title"]
        self.setWindowTitle(title)

        if "application_icon" in self.config:
            self.setWindowIcon(gui.create_icon(self.config["application_icon"]))

        self.on_key_pressed = NVPEvent()
        self.on_key_released = NVPEvent()

        # Set the default size:
        # self.setFixedSize(800, 600)

        # # Build the menu bar:
        # self.build_menu()

        # # Build the main toolbar:
        # self.build_main_toolbar()

        # Build the status bar:
        self.build_statusbar()

        # # build the internal widgets:
        # self.build_widgets()

    def build_statusbar(self):
        """Build the statusbar of the app."""

        status_bar = qwd.QStatusBar(self)
        # status_bar.setSizeGripEnabled(False)

        self.setStatusBar(status_bar)

    def set_status_message(self, msg):
        """Assing a status bar message."""
        self.statusBar().showMessage(msg)

    # def build_menu(self):
    #     """Build the menu bar"""

    #     mbar = self.menuBar()

    #     menu = mbar.addMenu("&File")
    #     act = qwd.QAction(gui.create_icon("folder-open-document"), 'Open file...', self)
    #     act.triggered.connect(self.open_a_file)
    #     menu.addAction(act)

    # def build_main_toolbar(self):
    #     """Build the main window toolbar"""
    #     toolbar = qwd.QToolBar("main_toolbar")
    #     toolbar.setIconSize(QtCore.QSize(16, 16))
    #     self.addToolBar(toolbar)

    #     btn = qwd.QAction(gui.create_icon("application-resize-full"), "Reset view", self)
    #     btn.setStatusTip("Reset the main view to fit the dataset")
    #     btn.triggered.connect(self.reset_view)
    #     # btn.setCheckable(True)
    #     toolbar.addAction(btn)

    def keyPressEvent(self, evt):  # pylint: disable=invalid-name
        """Handle key pressed event"""

        # logger.info("Key pressed: %s", evt.key())
        self.on_key_pressed.emit(evt)

    def keyReleaseEvent(self, evt):  # pylint: disable=invalid-name
        """Handle key released event"""

        # logger.info("Key released: %s", evt.key())
        self.on_key_released.emit(evt)

        # if e.key() == Qt.Key_F5:
        #     self.close()
