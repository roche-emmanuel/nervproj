import logging

from utils import TestBase

from nvp.math.vec3 import Vec3
from nvp.math.vec4 import Vec4

logger = logging.getLogger(__name__)


class Tests(TestBase):
    """Lat:lon array generation tests"""

    def test_lat_lon_gen(self):
        """Test generation of lat/lon arrays"""

        # Start with a satellite position as LLA coords:
        sat_lla = Vec3(0.0, 0.0, 500000.0)

        # Prepare the canonical frame at the satellite position:
        frame = self.get_canonical_frame(sat_lla)

        # logger.info("Frame is: %s", frame)

        # In this frame:
        # X should be Z_AXIS,
        # Y should be -Y_AXIS,
        # Z should be X_AXIS:

        pos = self.lla_to_ecef(sat_lla)
        self.assertVec3AlmostEqual(frame.col(0).xyz(), Vec3.Z_AXIS)
        self.assertVec3AlmostEqual(frame.col(1).xyz(), -Vec3.Y_AXIS)
        self.assertVec3AlmostEqual(frame.col(2).xyz(), Vec3.X_AXIS)
        self.assertVec3AlmostEqual(frame.col(3).xyz(), pos)
        self.assertVec3AlmostEqual(frame.row(3), Vec4(0, 0, 0, 1))
