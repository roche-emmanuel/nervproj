import logging
import math

from utils import TestBase

from nvp.math.mat4 import Mat4
from nvp.math.quat import Quat
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

        # Now we should construct the frame with X pointing towards the earth and Z pointing along the ECEF Z axis:
        rot = Mat4(Quat(math.pi / 2.0, Vec3.Y_AXIS))

        sat_frame = frame * rot
        self.assertVec3AlmostEqual(sat_frame.col(0).xyz(), -Vec3.X_AXIS)
        self.assertVec3AlmostEqual(sat_frame.col(1).xyz(), -Vec3.Y_AXIS)
        self.assertVec3AlmostEqual(sat_frame.col(2).xyz(), Vec3.Z_AXIS)
        self.assertVec3AlmostEqual(sat_frame.col(3).xyz(), pos)
        self.assertVec3AlmostEqual(sat_frame.row(3), Vec4(0, 0, 0, 1))

        # We now have a satellite frame with:
        # X pointing forward,
        # Y pointing left,
        # Z pointing up.

        # in this frame we need to define our grid of target points given
        # a horizontal FOV (in degrees) and a grid resolution:
        grid_width = 512
        grid_height = 256

        hfov = 45.0
        aspect = grid_width / grid_height

        # Compute our projection matrix as frustum:
