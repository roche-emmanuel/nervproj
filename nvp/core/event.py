"""Minimal event implementation module

This class can be used to connect and fire events synchronously."""


class NVPEvent(object):
    """Class representing a basic event"""

    def __init__(self):
        self.handlers = []

    def connect(self, handler):
        """Connect an event handler"""
        self.handlers.append(handler)
        return self

    def disconnect(self, handler):
        """Disconnect an event handler"""
        self.handlers.remove(handler)
        return self

    def emit(self, *args, **kwargs):
        """Emit this event"""
        for handler in self.handlers:
            handler(*args, **kwargs)

    def __iadd__(self, handler):
        return self.connect(handler)

    def __isub__(self, handler):
        return self.disconnect(handler)

    def __call__(self, *args, **kwargs):
        self.emit(*args, **kwargs)
