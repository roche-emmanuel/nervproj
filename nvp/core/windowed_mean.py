"""WindowedMean class definition"""
from collections import deque


class WindowedMean:
    """
    Class for efficiently computing a windowed mean on the last N values from a measurement.

    Attributes:
        window_size (int): The size of the window for computing the mean.
        values (deque): A deque to store the last N measurements.
        sum (float): The sum of the values in the window.

    Methods:
        add_value(value): Adds a new value to the window and updates the mean.
        get_mean(): Calculates and returns the mean of the values in the window.
    """

    def __init__(self, window_size):
        """
        Initialize the WindowedMean object.

        Args:
            window_size (int): The size of the window for computing the mean.
        """
        self.window_size = window_size
        self.values = deque(maxlen=window_size)
        self.sum = 0.0

    def add_value(self, value):
        """
        Add a new value to the window and update the mean.

        Args:
            value: The new measurement value.
        """
        if len(self.values) == self.window_size:
            # Subtract the oldest value from the sum
            self.sum -= self.values[0]

        # Add the new value to the deque and the sum
        self.values.append(value)
        self.sum += value

    def get_mean(self):
        """
        Calculate and return the mean of the values in the window.

        Returns:
            float: The computed mean.
        """
        if not self.values:
            return None  # Return None if no values are available
        return self.sum / len(self.values)
