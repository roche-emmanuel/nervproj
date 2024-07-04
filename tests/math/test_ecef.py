import logging

from utils import TestBase

from nvp.math.vec3 import Vec3

logger = logging.getLogger(__name__)

# Constants for WGS84 ellipsoid model
a = 6378137.0  # Semi-major axis
f = 1 / 298.257223563  # Flattening
e2 = 2 * f - f**2  # Square of eccentricity
b = a * (1 - f)  # Semi-minor axis


class Tests(TestBase):
    """ECEF tests"""

    def test_ecef_convert(self):
        """Convert ecef coords"""

        lla = Vec3(52.5200, 13.4050, 34)  # Berlin coordinates with 34m altitude
        ecef_coords = self.lla_to_ecef(lla)
        # print("ECEF:", ecef_coords)
        lla_coords = self.ecef_to_lla(ecef_coords)
        # print("LLA:", lla_coords)
        self.assertVec3AlmostEqual(lla_coords, lla)

    def test_equator_prime_meridian(self):
        """Check Equatorial position"""
        lla = Vec3(0.0, 0.0, 0.0)
        ecef = self.lla_to_ecef(lla)
        expected_ecef = Vec3(a, 0.0, 0.0)
        self.assertVec3AlmostEqual(ecef, expected_ecef)

        lla_converted = self.ecef_to_lla(ecef)
        self.assertVec3AlmostEqual(lla, lla_converted)

    def test_equator_90degs(self):
        """Check Equatorial position"""
        lla = Vec3(0.0, 90.0, 0.0)
        ecef = self.lla_to_ecef(lla)
        expected_ecef = Vec3(0.0, a, 0.0)
        self.assertVec3AlmostEqual(ecef, expected_ecef)

        lla_converted = self.ecef_to_lla(ecef)
        self.assertVec3AlmostEqual(lla, lla_converted)

    def test_north_pole(self):
        """Check north pole position"""
        lla = Vec3(90.0, 0.0, 0.0)
        ecef = self.lla_to_ecef(lla)
        expected_ecef = Vec3(0.0, 0.0, b)
        self.assertVec3AlmostEqual(ecef, expected_ecef)

        lla_converted = self.ecef_to_lla(ecef)
        self.assertVec3AlmostEqual(lla, lla_converted)

    def test_south_pole(self):
        """Check south pole position"""
        lla = Vec3(-90.0, 0.0, 0.0)
        ecef = self.lla_to_ecef(lla)
        expected_ecef = Vec3(0.0, 0.0, -b)
        self.assertVec3AlmostEqual(ecef, expected_ecef)

        lla_converted = self.ecef_to_lla(ecef)
        self.assertVec3AlmostEqual(lla, lla_converted)

    def test_date_line_east(self):
        """Check date line east position"""
        lla = Vec3(0.0, 180.0, 0.0)
        ecef = self.lla_to_ecef(lla)
        expected_ecef = Vec3(-a, 0.0, 0.0)
        self.assertVec3AlmostEqual(ecef, expected_ecef)

        lla_converted = self.ecef_to_lla(ecef)
        self.assertVec3AlmostEqual(lla, lla_converted)

    def test_date_line_west(self):
        """Check date line west position"""
        lla = Vec3(0.0, -180.0, 0.0)
        ecef = self.lla_to_ecef(lla)
        expected_ecef = Vec3(-a, 0.0, 0.0)
        self.assertVec3AlmostEqual(ecef, expected_ecef)

        lla_converted = self.ecef_to_lla(ecef)
        self.assertVec3AlmostEqual(lla, lla_converted)

    def test_consistency(self):
        """Test various locations"""
        test_cases = [
            Vec3(52.5200, 13.4050, 34),  # Berlin
            Vec3(34.0522, -118.2437, 71),  # Los Angeles
            Vec3(-33.8688, 151.2093, 58),  # Sydney
            Vec3(35.6895, 139.6917, 40),  # Tokyo
            Vec3(55.7558, 37.6176, 144),  # Moscow
        ]

        for lla in test_cases:
            with self.subTest(lla=lla):
                ecef = self.lla_to_ecef(lla)
                lla_converted = self.ecef_to_lla(ecef)
                self.assertVec3AlmostEqual(lla, lla_converted, delta=1e-5)
