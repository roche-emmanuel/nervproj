"""Simple Mat4 module"""

import copy
import math

from nvp.math.quat import Quat
from nvp.math.vec3 import Vec3
from nvp.math.vec4 import Vec4


class Mat4:
    """Mat4 class"""

    def __init__(self, *args):
        self._mat = [[0.0] * 4 for _ in range(4)]
        if len(args) == 0:
            self.make_identity()
        elif len(args) == 1 and isinstance(args[0], Mat4):
            self._mat = copy.deepcopy(args[0]._mat)
        elif len(args) == 1 and isinstance(args[0], Quat):
            self.make_rotate(args[0])
        elif len(args) == 16:
            self.set(*args)
        else:
            raise ValueError("Invalid arguments for Mat4 constructor")

    def __copy__(self):
        new_mat = Mat4()
        new_mat._mat = copy.deepcopy(self._mat)
        return new_mat

    def __eq__(self, other):
        if not isinstance(other, Mat4):
            return False
        return self._mat == other._mat

    def __ne__(self, other):
        return not self.__eq__(other)

    def __neg__(self):
        return self * -1.0

    def __getitem__(self, key):
        return self._mat[key]

    def __setitem__(self, key, value):
        self._mat[key] = value

    def __repr__(self):
        return f"Mat4({self._mat})"

    def compare(self, m):
        for r in range(4):
            for c in range(4):
                if self._mat[r][c] < m[r][c]:
                    return -1
                elif self._mat[r][c] > m[r][c]:
                    return 1
        return 0

    def __lt__(self, m):
        return self.compare(m) < 0

    def __gt__(self, m):
        return self.compare(m) > 0

    def __le__(self, m):
        return self.compare(m) <= 0

    def __ge__(self, m):
        return self.compare(m) >= 0

    def __add__(self, m):
        if isinstance(m, Mat4):
            new_mat = Mat4()
            for r in range(4):
                for c in range(4):
                    new_mat[r][c] = self._mat[r][c] + m[r][c]
            return new_mat
        else:
            raise TypeError("Unsupported operand type(s) for +: 'Mat4' and " + str(type(m)))

    def __sub__(self, m):
        if isinstance(m, Mat4):
            new_mat = Mat4()
            for r in range(4):
                for c in range(4):
                    new_mat[r][c] = self._mat[r][c] - m[r][c]
            return new_mat
        else:
            raise TypeError("Unsupported operand type(s) for -: 'Mat4' and " + str(type(m)))

    def __mul__(self, m):
        if isinstance(m, Mat4):
            new_mat = Mat4()
            for r in range(4):
                for c in range(4):
                    new_mat[r][c] = sum(self._mat[r][k] * m[k][c] for k in range(4))
            return new_mat
        elif isinstance(m, (int, float)):
            new_mat = Mat4()
            for r in range(4):
                for c in range(4):
                    new_mat[r][c] = self._mat[r][c] * m
            return new_mat
        elif isinstance(m, Vec4):
            new_vec = Vec4(
                sum(self._mat[0][i] * m[i] for i in range(4)),
                sum(self._mat[1][i] * m[i] for i in range(4)),
                sum(self._mat[2][i] * m[i] for i in range(4)),
                sum(self._mat[3][i] * m[i] for i in range(4)),
            )
            return new_vec
        elif isinstance(m, Vec3):
            new_vec = Vec3(
                sum(self._mat[0][i] * m[i] for i in range(3)) + self._mat[0][3],
                sum(self._mat[1][i] * m[i] for i in range(3)) + self._mat[1][3],
                sum(self._mat[2][i] * m[i] for i in range(3)) + self._mat[2][3],
            )
            return new_vec
        else:
            raise TypeError("Unsupported operand type(s) for *: 'Mat4' and " + str(type(m)))

    def __rmul__(self, m):
        if isinstance(m, (int, float)):
            return self.__mul__(m)
        else:
            raise TypeError("Unsupported operand type(s) for *: " + str(type(m)) + " and 'Mat4'")

    def make_identity(self):
        self._mat = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

    def set(self, *args):
        if len(args) != 16:
            raise ValueError("Invalid number of arguments for set method")
        idx = 0
        for i in range(4):
            for j in range(4):
                self._mat[i][j] = args[idx]
                idx += 1

    def transposed(self):
        new_mat = Mat4()
        for r in range(4):
            for c in range(4):
                new_mat[r][c] = self._mat[c][r]
        return new_mat

    def set_rotate(self, q):
        """Set this matrix as a rotation"""
        length2 = q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w
        if math.fabs(length2) <= 1e-6:
            for r in range(3):
                for c in range(3):
                    self._mat[r][c] = 0.0
        else:
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
            self._mat[0][0] = 1.0 - (yy + zz)
            self._mat[0][1] = xy - wz
            self._mat[0][2] = xz + wy
            self._mat[1][0] = xy + wz
            self._mat[1][1] = 1.0 - (xx + zz)
            self._mat[1][2] = yz - wx
            self._mat[2][0] = xz - wy
            self._mat[2][1] = yz + wx
            self._mat[2][2] = 1.0 - (xx + yy)

    def get_rotate(self):
        q = Quat()
        tq = [0.0] * 4
        tq[0] = 1.0 + self._mat[0][0] + self._mat[1][1] + self._mat[2][2]
        tq[1] = 1.0 + self._mat[0][0] - self._mat[1][1] - self._mat[2][2]
        tq[2] = 1.0 - self._mat[0][0] + self._mat[1][1] - self._mat[2][2]
        tq[3] = 1.0 - self._mat[0][0] - self._mat[1][1] + self._mat[2][2]
        j = 0
        for i in range(1, 4):
            if tq[i] > tq[j]:
                j = i
        if j == 0:
            q.w = tq[0]
            q.x = self._mat[2][1] - self._mat[1][2]
            q.y = self._mat[0][2] - self._mat[2][0]
            q.z = self._mat[1][0] - self._mat[0][1]
        elif j == 1:
            q.x = tq[1]
            q.w = self._mat[2][1] - self._mat[1][2]
            q.y = self._mat[1][0] + self._mat[0][1]
            q.z = self._mat[0][2] + self._mat[2][0]
        elif j == 2:
            q.y = tq[2]
            q.w = self._mat[0][2] - self._mat[2][0]
            q.x = self._mat[1][0] + self._mat[0][1]
            q.z = self._mat[2][1] + self._mat[1][2]
        elif j == 3:
            q.z = tq[3]
            q.w = self._mat[1][0] - self._mat[0][1]
            q.x = self._mat[0][2] + self._mat[2][0]
            q.y = self._mat[2][1] + self._mat[1][2]
        s = math.sqrt(0.25 / tq[j])
        q.w *= s
        q.x *= s
        q.y *= s
        q.z *= s
        return q

    def col(self, i):
        """Get a specific column"""
        return Vec4(self._mat[0][i], self._mat[1][i], self._mat[2][i], self._mat[3][i])

    def row(self, i):
        """Get a specific row"""
        return Vec4(self._mat[i][0], self._mat[i][1], self._mat[i][2], self._mat[i][3])

    def is_identity(self):
        return self._mat == [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

    def make_scale(self, x, y, z):
        self.make_identity()
        self._mat[0][0] = x
        self._mat[1][1] = y
        self._mat[2][2] = z

    def make_translate(self, x, y, z):
        self.make_identity()
        self._mat[0][3] = x
        self._mat[1][3] = y
        self._mat[2][3] = z

    def make_rotate(self, *args):
        if len(args) == 2 and isinstance(args[0], Vec3) and isinstance(args[1], Vec3):
            from_vec = args[0]
            to_vec = args[1]
            self.make_identity()
            quat = Quat()
            quat.make_rotate(from_vec, to_vec)
            self.set_rotate(quat)
        elif len(args) == 2 and isinstance(args[0], (float, int)) and isinstance(args[1], Vec3):
            angle = args[0]
            axis = args[1]
            self.make_identity()
            quat = Quat()
            quat.make_rotate(angle, axis)
            self.set_rotate(quat)
        elif len(args) == 4 and all(isinstance(arg, (float, int)) for arg in args):
            angle1 = args[0]
            axis1 = Vec3(args[1], args[2], args[3])
            self.make_identity()
            quat = Quat()
            quat.make_rotate(angle1, axis1)
            self.set_rotate(quat)
        elif len(args) == 1 and isinstance(args[0], Quat):
            quat = args[0]
            self.make_identity()
            self.set_rotate(quat)
        elif (
            len(args) == 6
            and all(isinstance(arg, (float, int)) for arg in args[::2])
            and all(isinstance(arg, Vec3) for arg in args[1::2])
        ):
            angle1, axis1, angle2, axis2, angle3, axis3 = args
            self.make_identity()
            quat = Quat()
            quat.make_rotate(angle1, axis1, angle2, axis2, angle3, axis3)
            self.set_rotate(quat)
        else:
            raise ValueError("Invalid arguments for make_rotate")

    def make_perspective(self, fovy, aspect_ratio, zNear, zFar):
        """Set to a symmetrical perspective projection. assuming fovy in radians"""

        if zNear == 0.0 or (zFar - zNear) == 0.0:
            # Handle invalid projection values
            raise ValueError("Invalid zNear/zFar values")

        B = 1.0 / math.tan(fovy / 2.0)
        A = B / aspect_ratio
        C = zFar / (zFar - zNear)
        D = -zFar * zNear / (zFar - zNear)

        self._mat = [[A, 0.0, 0.0, 0.0], [0.0, B, 0.0, 0.0], [0.0, 0.0, C, D], [0.0, 0.0, 1.0, 0.0]]

    def get_perspective(self):
        """Get the frustum settings of a symmetric perspective projection matrix."""
        if self._mat[3][0] != 0.0 or self._mat[3][1] != 0.0 or self._mat[3][2] != 1.0 or self._mat[3][3] != 0.0:
            raise ValueError("Invalid perspective matrix")

        fovy = 2.0 * math.atan(1.0 / self._mat[1][1])
        aspect_ratio = self._mat[1][1] / self._mat[0][0]
        zNear = -self._mat[2][3] / self._mat[2][2]
        zFar = zNear * self._mat[2][2] / (self._mat[2][2] - 1.0)

        return fovy, aspect_ratio, zNear, zFar

    def invert(self, rhs):
        """Invert the matrix rhs, automatically select invert_4x3 or invert_4x4."""
        is_4x3 = rhs[0][3] == 0.0 and rhs[1][3] == 0.0 and rhs[2][3] == 0.0 and rhs[3][3] == 1.0
        if is_4x3:
            return self.invert_4x3(rhs)
        else:
            return self.invert_4x4(rhs)

    def inverse(self):
        """Return the inverse of the matrix."""
        m = Mat4()
        m.invert(self)
        return m

    def invert_4x3(self, mat):
        """Invert a 4x3 matrix (no perspective)."""
        if mat is self:
            tm = Mat4(mat)
            return self.invert_4x3(tm)

        r00 = mat[0][0]
        r01 = mat[0][1]
        r02 = mat[0][2]
        r10 = mat[1][0]
        r11 = mat[1][1]
        r12 = mat[1][2]
        r20 = mat[2][0]
        r21 = mat[2][1]
        r22 = mat[2][2]

        det = r00 * (r11 * r22 - r12 * r21) + r01 * (r12 * r20 - r10 * r22) + r02 * (r10 * r21 - r11 * r20)

        if abs(det) < 1e-6:
            return False

        one_over_det = 1.0 / det

        self[0][0] = (r11 * r22 - r12 * r21) * one_over_det
        self[0][1] = (r02 * r21 - r01 * r22) * one_over_det
        self[0][2] = (r01 * r12 - r02 * r11) * one_over_det
        self[0][3] = 0.0

        self[1][0] = (r12 * r20 - r10 * r22) * one_over_det
        self[1][1] = (r00 * r22 - r02 * r20) * one_over_det
        self[1][2] = (r02 * r10 - r00 * r12) * one_over_det
        self[1][3] = 0.0

        self[2][0] = (r10 * r21 - r11 * r20) * one_over_det
        self[2][1] = (r01 * r20 - r00 * r21) * one_over_det
        self[2][2] = (r00 * r11 - r01 * r10) * one_over_det
        self[2][3] = 0.0

        self[3][0] = 0.0
        self[3][1] = 0.0
        self[3][2] = 0.0
        self[3][3] = 1.0

        return True

    def invert_4x4(self, mat):
        """Invert a full 4x4 matrix."""
        if mat is self:
            tm = Mat4(mat)
            return self.invert_4x4(tm)

        temp = Mat4(mat)

        indxc = [0, 0, 0, 0]
        indxr = [0, 0, 0, 0]
        ipiv = [0, 0, 0, 0]

        for i in range(4):
            irow = 0
            icol = 0
            big = 0.0

            # Choose pivot
            for j in range(4):
                if ipiv[j] != 1:
                    for k in range(4):
                        if ipiv[k] == 0:
                            if abs(temp[j][k]) >= big:
                                big = abs(temp[j][k])
                                irow = j
                                icol = k
                        elif ipiv[k] > 1:
                            raise ValueError("Matrix is singular.")

            ipiv[icol] += 1

            if irow != icol:
                for k in range(4):
                    temp[irow][k], temp[icol][k] = temp[icol][k], temp[irow][k]

            indxr[i] = irow
            indxc[i] = icol

            if temp[icol][icol] == 0.0:
                raise ValueError("Matrix is singular.")

            pivinv = 1.0 / temp[icol][icol]
            temp[icol][icol] = 1.0

            for j in range(4):
                temp[icol][j] *= pivinv

            for j in range(4):
                if j != icol:
                    dum = temp[j][icol]
                    temp[j][icol] = 0.0
                    for k in range(4):
                        temp[j][k] -= temp[icol][k] * dum

        for i in range(3, -1, -1):
            if indxr[i] != indxc[i]:
                for j in range(4):
                    temp[j][indxr[i]], temp[j][indxc[i]] = temp[j][indxc[i]], temp[j][indxr[i]]

        self[:] = temp[:]
        return True

    @staticmethod
    def translate(*args):
        """Static method to create a translation matrix."""
        m = Mat4()
        if len(args) == 1 and isinstance(args[0], Vec3):
            m.make_translate(args[0].x, args[0].y, args[0].z)
        elif len(args) == 3 and all(isinstance(arg, (int, float)) for arg in args):
            m.make_translate(args[0], args[1], args[2])
        else:
            raise ValueError("Invalid arguments provided to translate method")
        return m

    @staticmethod
    def rotate(*args):
        """Static method to create a rotation matrix."""
        m = Mat4()
        if len(args) == 2 and isinstance(args[0], Vec3) and isinstance(args[1], Vec3):
            m.make_rotate(args[0], args[1])
        elif (
            len(args) == 4
            and all(isinstance(arg, (int, float)) for arg in args[:3])
            and isinstance(args[3], (int, float))
        ):
            m.make_rotate(args[0], args[1], args[2], args[3])
        elif len(args) == 2 and isinstance(args[0], (int, float)) and isinstance(args[1], Vec3):
            m.make_rotate(args[0], args[1])
        elif (
            len(args) == 6
            and all(isinstance(arg, (int, float)) for arg in args[:3])
            and all(isinstance(arg, Vec3) for arg in args[3:6])
        ):
            m.make_rotate(args[0], args[1], args[2], args[3], args[4], args[5])
        elif len(args) == 1 and isinstance(args[0], Quat):
            m.make_rotate(args[0])
        else:
            raise ValueError("Invalid arguments provided to rotate method")
        return m

    @staticmethod
    def scale(*args):
        """Static method to create a scaling matrix."""
        m = Mat4()
        if len(args) == 1 and isinstance(args[0], Vec3):
            m.make_scale(args[0].x, args[0].y, args[0].z)
        elif len(args) == 3 and all(isinstance(arg, (int, float)) for arg in args):
            m.make_scale(args[0], args[1], args[2])
        else:
            raise ValueError("Invalid arguments provided to scale method")
        return m

    @staticmethod
    def perspective(fovy, aspect_ratio, z_near, z_far):
        """Create a perspective projection matrix."""
        m = Mat4()
        m.make_perspective(fovy, aspect_ratio, z_near, z_far)
        return m
