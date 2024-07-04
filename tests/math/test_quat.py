"""Unit tests on Quat"""

import logging
import math

from utils import TestBase

from nvp.math.quat import Quat

logger = logging.getLogger(__name__)


class Tests(TestBase):
    """Quat tests"""

    def test_identity_matrix(self):
        """Test default identity quat"""
        q = Quat(0, 0, 0, 1)

        length2 = q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w
        assert length2 == 1.0

        rlength2 = 2.0 / length2
        x2 = q.x * rlength2
        y2 = q.y * rlength2
        z2 = q.z * rlength2
        xx = q.x * x2
        xy = q.x * y2
        xz = q.x * z2
        yy = q.y * y2
        yz = q.y * z2
        zz = q.z * z2
        wx = q.w * x2
        wy = q.w * y2
        wz = q.w * z2

        eps = 1e-6
        assert math.isclose(1.0 - (yy + zz), 1.0, abs_tol=eps)
        assert math.isclose(xy - wz, 0.0, abs_tol=eps)
        assert math.isclose(xz + wy, 0.0, abs_tol=eps)
        assert math.isclose(xy + wz, 0.0, abs_tol=eps)
        assert math.isclose(1.0 - (xx + zz), 1.0, abs_tol=eps)
        assert math.isclose(yz - wx, 0.0, abs_tol=eps)
        assert math.isclose(xz - wy, 0.0, abs_tol=eps)
        assert math.isclose(yz + wx, 0.0, abs_tol=eps)
        assert math.isclose(1.0 - (xx + yy), 1.0, abs_tol=eps)
