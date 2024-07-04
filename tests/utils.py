"""Base class used for all unit tests"""

import logging
from unittest import TestCase

import numpy as np

from nvp.math.mat4 import Mat4
from nvp.math.vec3 import Vec3

logger = logging.getLogger(__name__)


# Constants for WGS84 ellipsoid model
a = 6378137.0  # Semi-major axis
f = 1 / 298.257223563  # Flattening
e2 = 2 * f - f**2  # Square of eccentricity


def format_msg(msg, *args):
    """Format a provided message with args"""
    if args:
        return msg % args

    return msg


class TestBase(TestCase):
    """Basic tests base class"""

    def __init__(self, *args):
        """Constructor"""
        TestCase.__init__(self, *args)

    def log(self, msg, *args):
        """Log a normal message"""
        logger.info(format_msg(msg, *args))

    def assertVec3AlmostEqual(self, v1, v2, delta=1e-6):
        """Test 2 vec3 are almost equal"""
        self.assertAlmostEqual(v1.x, v2.x, delta=delta)
        self.assertAlmostEqual(v1.y, v2.y, delta=delta)
        self.assertAlmostEqual(v1.z, v2.z, delta=delta)

    def assertVec4AlmostEqual(self, v1, v2, delta=1e-6):
        """Test 2 vec4 are almost equal"""
        self.assertAlmostEqual(v1.x, v2.x, delta=delta)
        self.assertAlmostEqual(v1.y, v2.y, delta=delta)
        self.assertAlmostEqual(v1.z, v2.z, delta=delta)
        self.assertAlmostEqual(v1.w, v2.w, delta=delta)

    def assertQuatAlmostEqual(self, v1, v2, delta=1e-6):
        """Test 2 quat are almost equal"""
        self.assertAlmostEqual(v1.x, v2.x, delta=delta)
        self.assertAlmostEqual(v1.y, v2.y, delta=delta)
        self.assertAlmostEqual(v1.z, v2.z, delta=delta)
        self.assertAlmostEqual(v1.w, v2.w, delta=delta)

    def lla_to_ecef(self, lla):
        """Convert latitude, longitude, and altitude to ECEF coordinates"""
        lat, lon = np.radians(lla.x), np.radians(lla.y)
        alt = lla.z

        N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
        x = (N + alt) * np.cos(lat) * np.cos(lon)
        y = (N + alt) * np.cos(lat) * np.sin(lon)
        z = (N * (1 - e2) + alt) * np.sin(lat)

        return Vec3(x, y, z)

    def ecef_to_lla(self, ecef):
        """Convert ECEF coordinates to latitude, longitude, and altitude"""
        x, y, z = ecef.x, ecef.y, ecef.z

        lon = np.arctan2(y, x)
        p = np.sqrt(x**2 + y**2)
        lat = np.arctan2(z, p * (1 - e2))  # Initial latitude guess

        lat_prev = 0
        while np.abs(lat - lat_prev) > 1e-9:
            lat_prev = lat
            N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
            lat = np.arctan2(z + e2 * N * np.sin(lat), p)

        N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
        alt = p / np.cos(lat) - N

        lat, lon = np.degrees(lat), np.degrees(lon)
        return Vec3(lat, lon, alt)

    def get_canonical_frame(self, lla):
        """Construct the canonical frame at a given lla location"""

        # Build the up vector precisely:
        pos = self.lla_to_ecef(lla)
        pos1 = self.lla_to_ecef(lla + Vec3(0.0, 0.0, 10000.0))

        up = (pos1 - pos).normalized()
        # logger.info("Up vector is: %s", up)

        west = up.cross(Vec3.Z_AXIS)
        west.normalize()

        north = west.cross(up)
        north.normalize()

        return Mat4(
            north.x, west.x, up.x, pos.x, north.y, west.y, up.y, pos.y, north.z, west.z, up.z, pos.z, 0.0, 0.0, 0.0, 1.0
        )
