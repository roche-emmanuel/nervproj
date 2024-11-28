"""AtomicInteger class."""

from threading import Lock


class AtomicInteger:
    """AtomicInteger class."""

    def __init__(self, initial_value=0):
        """Constructor."""
        self._value = initial_value
        self._lock = Lock()

    def get(self):
        """Get the current value."""
        with self._lock:
            return self._value

    def set(self, value):
        """Set the current value."""
        with self._lock:
            self._value = value

    def increment(self):
        """Increment the value by one."""
        with self._lock:
            self._value += 1
            return self._value

    def decrement(self):
        """Decrement the value by one."""
        with self._lock:
            self._value -= 1
            return self._value

    def add(self, delta):
        """Add a given value."""
        with self._lock:
            self._value += delta
            return self._value

    def compare_and_set(self, expected, new_value):
        """Set the value if it matches expectation."""
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False
