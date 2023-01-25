"""Module for AppBase class definition"""

import logging
import sys

from PyQt5.QtCore import QMutex, QMutexLocker, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication

from nvp.gui.main_window import MainWindow
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class EventSignal(QObject):
    """Simple class used to hold an event"""

    event = pyqtSignal(object)


class MainSignals(QObject):
    """Signal provider for the main thread."""

    task_received = pyqtSignal(object)


class AppBase(NVPComponent):
    """AppBase component class"""

    def __init__(self, ctx: NVPContext, app_name: str):
        """class constructor, should provide an app name that will be used
        to select the config element to load."""

        NVPComponent.__init__(self, ctx)
        self.app_name = app_name
        self.config = self.config.get(app_name, {})
        self.app = None
        self.main_window = None
        self.main_thread_id = None
        self.signals = None
        self.events = {}

        self.app_dir = None

    def on_event(self, evt_name, func):
        """Connect an event handler to a given event."""
        assert self.is_main_thread(), "Expected to be on the main thread here."

        if evt_name not in self.events:
            self.events[evt_name] = EventSignal()

        self.events[evt_name].event.connect(func)

    def emit(self, evt_name, data=None):
        """Emit an event, no effect if there is no connection."""
        if evt_name in self.events:
            self.events[evt_name].event.emit(data)

    def get_app_dir(self):
        """Retrieve the base application dir"""
        self.check(self.app_dir is not None, "app dir not specified for %s", self.__class__.__name__)
        return self.app_dir

    def get_app(self):
        """Retrieve the Qapplication"""
        return self.app

    def get_config(self):
        """Retrieve the config for this application"""
        return self.config

    def get_main_window(self):
        """Retrieve the main window of the application"""
        return self.main_window

    def build_app(self):
        """Build the application."""

        # Simple base build of an empty application:
        self.app = QApplication(sys.argv)

        self.main_window = MainWindow(self)

    def is_main_thread(self):
        """Check if we are on the main application thread."""
        assert self.main_thread_id is not None, "Main ThreadID not set yet."
        return self.main_thread_id == self.get_thread_id()

    def on_task_received(self, desc):
        """Execute a task on the main thread."""
        assert self.is_main_thread(), "Should be on the main thread here."

        # We execute the task:
        func = desc["func"]
        args = desc["args"]
        kwargs = desc["kwargs"]
        func(*args, **kwargs)

    def create_mutex(self):
        """Create a new mutex"""
        return QMutex()

    def create_mutex_guard(self, mutex):
        """Create a guard on a mutex"""
        return QMutexLocker(mutex)

    def run_app(self):
        """Run the application."""

        # This is the main thread, so we set this up here:
        self.main_thread_id = self.get_thread_id()
        logger.info("Main thread ID: %d", self.main_thread_id)

        self.signals = MainSignals()
        self.signals.task_received.connect(self.on_task_received)

        # First we build the app:
        self.build_app()

        # Display the main window:
        self.main_window.show()

        # Run the event loop:
        self.app.exec()

    def post_main_task(self, func, *args, **kwargs):
        """Post a task on the main thread."""
        assert func is not None, "Invalid task."
        self.signals.task_received.emit({"func": func, "args": args, "kwargs": kwargs})

    def post_status_message(self, msg):
        """Post a status message on the main window."""
        if self.is_main_thread():
            self.main_window.set_status_message(msg)
        else:
            self.post_main_task(lambda: self.post_status_message(msg))

    def post_task(self, func, name=None, on_done=None, on_error=None, on_progress=None):
        """Post a task on the QTask manager."""
        tman = self.get_component("qtasks")
        tman.add_task(func, name=name, on_done=on_done, on_error=on_error, on_progress=on_progress)
