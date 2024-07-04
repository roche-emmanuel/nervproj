"""Unit tests on Mat4"""

import logging
import math

from utils import TestBase

from nvp.math.mat4 import Mat4
from nvp.math.quat import Quat
from nvp.math.vec3 import Vec3
from nvp.math.vec4 import Vec4

logger = logging.getLogger(__name__)


class Tests(TestBase):
    """Mat4 tests"""

    def test_identity_matrix(self):
        """Test default identity matrix"""
        mat = Mat4()
        expected_identity = Mat4()
        self.assertTrue(mat.is_identity())
        self.assertEqual(mat, expected_identity)

    def test_rotation_from_quaternion(self):
        """Test constructing Mat4 from Quat"""
        quat = Quat(0, 0, 0, 1)  # Identity quaternion
        mat = Mat4(quat)
        expected_identity = Mat4()
        self.assertEqual(mat, expected_identity)

    def test_matrix_multiplication(self):
        """Test matrix multiplication"""
        mat1 = Mat4()
        mat2 = Mat4()
        result = mat1 * mat2
        expected = Mat4()
        self.assertEqual(result, expected)

    def test_rotation_axis_angle(self):
        """Test rotation matrix creation from axis-angle"""
        angle = math.pi / 2
        axis = Vec3(0, 0, 1)  # Rotate around z-axis
        mat = Mat4()
        mat.make_rotate(angle, axis)
        vec = Vec4(1, 0, 0, 1)  # x-axis unit vector
        rotated_vec = mat * vec
        expected_vec = Vec4(0, 1, 0, 1)  # Should be y-axis unit vector
        self.assertVec4AlmostEqual(rotated_vec, expected_vec)

    def test_rotate_from_two_vectors(self):
        """Test rotation matrix creation from two vectors"""
        from_vec = Vec3(1, 0, 0)
        to_vec = Vec3(0, 1, 0)
        mat = Mat4()
        mat.make_rotate(from_vec, to_vec)
        vec = Vec4(1, 0, 0, 1)
        rotated_vec = mat * vec
        expected_vec = Vec4(0, 1, 0, 1)
        self.assertVec4AlmostEqual(rotated_vec, expected_vec)

    def test_quaternion_to_matrix(self):
        """Test quaternion to matrix and back"""
        quat = Quat(math.sqrt(2) / 2, 0, math.sqrt(2) / 2, 0)  # 90 degrees around x-axis
        mat = Mat4(quat)
        recovered_quat = mat.get_rotate()
        self.assertQuatAlmostEqual(quat, recovered_quat)

    def test_matrix_scalar_multiplication(self):
        """Test matrix and scalar multiplication"""
        mat = Mat4()
        scalar = 2
        result = mat * scalar
        expected = Mat4(2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2)
        self.assertEqual(result, expected)

    def test_matrix_vec4_multiplication(self):
        """Test matrix and Vec4 multiplication"""
        mat = Mat4()
        vec = Vec4(1, 0, 0, 1)
        result = mat * vec
        expected = Vec4(1, 0, 0, 1)
        self.assertVec4AlmostEqual(result, expected)

    def test_matrix_vec3_multiplication(self):
        """Test matrix and Vec3 multiplication"""
        mat = Mat4()
        vec = Vec3(1, 0, 0)
        result = mat * vec
        expected = Vec3(1, 0, 0)
        self.assertVec3AlmostEqual(result, expected)

    def test_perspective(self):
        """Test perspective setup"""

        mat = Mat4()

        # Set perspective projection
        mat.make_perspective(math.radians(60.0), 16.0 / 9.0, 0.1, 100.0)

        # Retrieve perspective parameters
        fovy, aspect_ratio, zNear, zFar = mat.get_perspective()

        eps = 1e-6
        self.assertAlmostEqual(fovy, math.radians(60), delta=eps)
        self.assertAlmostEqual(aspect_ratio, 16 / 9, delta=eps)
        self.assertAlmostEqual(zNear, 0.1, delta=eps)
        self.assertAlmostEqual(zFar, 100.0, delta=eps)

    def test_invert(self):
        """Test inverting matrix"""

        for _ in range(10):

            tx = Vec3(self.gen_float(-100, 100), self.gen_float(-100, 100), self.gen_float(-100, 100))
            angle = self.gen_float(-100, 100)
            axis = Vec3(self.gen_float(-100, 100), self.gen_float(-100, 100), self.gen_float(-100, 100))
            scale = Vec3(self.gen_float(-100, 100), self.gen_float(-100, 100), self.gen_float(-100, 100))

            m0 = Mat4.translate(tx)
            m1 = Mat4.rotate(angle, axis)
            m2 = Mat4.scale(scale)

            m0inv = m0.inverse()

            # logger.info("m0 is: %s", m0)
            # logger.info("m0inv is: %s", m0inv)
            assert (-tx).x == -tx.x

            self.assertVec3AlmostEqual(m0inv.col(3).xyz(), -tx)

            m = m0 * m1 * m2
            minv = m.inverse()

            minv2 = minv.inverse()

            # logger.info("M is: %s", m)
            # logger.info("Minv is: %s", minv)

            # # self.assertVec4AlmostEqual(m0.col(0), Vec4(1, 2, 3, 4))

            self.assertMat4AlmostEqual(m, minv2)
