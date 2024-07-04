"""Simple quat class"""

import math

from nvp.math.vec3 import Vec3
from nvp.math.vec4 import Vec4


class Quat:
    """Quat class"""

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 1.0):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def __getitem__(self, i: int) -> float:
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        elif i == 2:
            return self.z
        elif i == 3:
            return self.w
        else:
            raise IndexError("Quat index out of range")

    def __setitem__(self, i: int, value: float) -> None:
        if i == 0:
            self.x = value
        elif i == 1:
            self.y = value
        elif i == 2:
            self.z = value
        elif i == 3:
            self.w = value
        else:
            raise IndexError("Quat index out of range")

    def __eq__(self, other: "Quat") -> bool:
        return self.x == other.x and self.y == other.y and self.z == other.z and self.w == other.w

    def __ne__(self, other: "Quat") -> bool:
        return not self == other

    def __lt__(self, other: "Quat") -> bool:
        return tuple(self) < tuple(other)

    def __mul__(self, rhs: "Quat") -> "Quat":
        return self.mult(rhs)

    def __imul__(self, rhs: "Quat") -> "Quat":
        self.post_mult(rhs)
        return self

    def __truediv__(self, denom: float) -> "Quat":
        return self.mult(self.inverse())

    def __itruediv__(self, denom: "Quat") -> "Quat":
        self *= denom.inverse()
        return self

    def __add__(self, rhs: "Quat") -> "Quat":
        return Quat(self.x + rhs.x, self.y + rhs.y, self.z + rhs.z, self.w + rhs.w)

    def __iadd__(self, rhs: "Quat") -> "Quat":
        self.x += rhs.x
        self.y += rhs.y
        self.z += rhs.z
        self.w += rhs.w
        return self

    def __sub__(self, rhs: "Quat") -> "Quat":
        return Quat(self.x - rhs.x, self.y - rhs.y, self.z - rhs.z, self.w - rhs.w)

    def __isub__(self, rhs: "Quat") -> "Quat":
        self.x -= rhs.x
        self.y -= rhs.y
        self.z -= rhs.z
        self.w -= rhs.w
        return self

    def __neg__(self) -> "Quat":
        return Quat(-self.x, -self.y, -self.z, -self.w)

    def __len__(self) -> int:
        return 4

    def mult(self, rhs: "Quat") -> "Quat":
        """multiply quat"""
        return Quat(
            self.w * rhs.x + self.x * rhs.w + self.y * rhs.z - self.z * rhs.y,
            self.w * rhs.y - self.x * rhs.z + self.y * rhs.w + self.z * rhs.x,
            self.w * rhs.z + self.x * rhs.y - self.y * rhs.x + self.z * rhs.w,
            self.w * rhs.w - self.x * rhs.x - self.y * rhs.y - self.z * rhs.z,
        )

    def post_mult(self, rhs: "Quat") -> None:
        """Post multiply"""
        x = self.w * rhs.x + self.x * rhs.w + self.y * rhs.z - self.z * rhs.y
        y = self.w * rhs.y - self.x * rhs.z + self.y * rhs.w + self.z * rhs.x
        z = self.w * rhs.z + self.x * rhs.y - self.y * rhs.x + self.z * rhs.w
        self.w = self.w * rhs.w - self.x * rhs.x - self.y * rhs.y - self.z * rhs.z
        self.z = z
        self.y = y
        self.x = x

    def inverse(self) -> "Quat":
        """Invert quat"""
        return self.conj() / self.length2()

    def conj(self) -> "Quat":
        """conjugate quat"""
        return Quat(-self.x, -self.y, -self.z, self.w)

    def length(self) -> float:
        """Get length"""
        return math.sqrt(self.length2())

    def length2(self) -> float:
        """get length2"""
        return self.x * self.x + self.y * self.y + self.z * self.z + self.w * self.w

    def set_identity(self) -> None:
        """set to identity"""
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.w = 1.0

    def as_vec4(self) -> Vec4:
        """Convert to vec4"""
        return Vec4(self.x, self.y, self.z, self.w)

    def as_vec3(self) -> Vec3:
        """Convert the vec3"""
        return Vec3(self.x, self.y, self.z)

    def __str__(self) -> str:
        return f"({self.x}, {self.y}, {self.z}, {self.w})"

    def set(self, *args):
        """Set this quat"""
        if len(args) == 1 and isinstance(args[0], Quat):
            self.x = args[0].x
            self.y = args[0].y
            self.z = args[0].z
            self.w = args[0].w
        elif len(args) == 4:
            self.x = args[0]
            self.y = args[1]
            self.z = args[2]
            self.w = args[3]
        else:
            raise ValueError("Invalid arguments for set")

    def make_rotate(self, *args):
        """Set the quat to represent various types of rotations."""
        if len(args) == 2 and isinstance(args[0], (float, int)) and isinstance(args[1], Vec3):
            angle, vec = args
            self._make_rotate_angle_vec(angle, vec)
        elif len(args) == 4 and all(isinstance(arg, (float, int)) for arg in args):
            angle, x, y, z = args
            self._make_rotate_angle_xyz(angle, x, y, z)
        elif (
            len(args) == 6
            and isinstance(args[0], (float, int))
            and isinstance(args[1], Vec3)
            and isinstance(args[2], (float, int))
            and isinstance(args[3], Vec3)
            and isinstance(args[4], (float, int))
            and isinstance(args[5], Vec3)
        ):
            angle1, axis1, angle2, axis2, angle3, axis3 = args
            self._make_rotate_three_axes(angle1, axis1, angle2, axis2, angle3, axis3)
        elif len(args) == 2 and all(isinstance(arg, Vec3) for arg in args):
            vec1, vec2 = args
            self._make_rotate_vec_to_vec(vec1, vec2)
        else:
            raise ValueError("Invalid arguments for make_rotate")

    def _make_rotate_angle_xyz(self, angle, x, y, z):
        epsilon = 1e-7
        length = math.sqrt(x * x + y * y + z * z)
        if length < epsilon:
            self.x = 0
            self.y = 0
            self.z = 0
            self.w = 1
            return

        inversenorm = 1.0 / length
        coshalfangle = math.cos(0.5 * angle)
        sinhalfangle = math.sin(0.5 * angle)

        self.x = x * sinhalfangle * inversenorm
        self.y = y * sinhalfangle * inversenorm
        self.z = z * sinhalfangle * inversenorm
        self.w = coshalfangle

    def _make_rotate_angle_vec(self, angle, vec):
        self._make_rotate_angle_xyz(angle, vec.x, vec.y, vec.z)

    def _make_rotate_three_axes(self, angle1, axis1, angle2, axis2, angle3, axis3):
        q1 = Quat()
        q1._make_rotate_angle_vec(angle1, axis1)
        q2 = Quat()
        q2._make_rotate_angle_vec(angle2, axis2)
        q3 = Quat()
        q3._make_rotate_angle_vec(angle3, axis3)

        self.set(q3.mult(q2).mult(q1))

    def _make_rotate_vec_to_vec(self, vec1, vec2):
        sourceVector = vec1
        targetVector = vec2

        fromLen2 = vec1.length2()
        toLen2 = vec2.length2()

        if fromLen2 < 1.0 - 1e-7 or fromLen2 > 1.0 + 1e-7:
            sourceVector = vec1.normalize()
        if toLen2 < 1.0 - 1e-7 or toLen2 > 1.0 + 1e-7:
            targetVector = vec2.normalize()

        dotProdPlus1 = 1.0 + sourceVector.dot(targetVector)

        if dotProdPlus1 < 1e-7:
            if abs(sourceVector.x) < 0.6:
                norm = math.sqrt(1.0 - sourceVector.x * sourceVector.x)
                self.x = 0.0
                self.y = sourceVector.z / norm
                self.z = -sourceVector.y / norm
                self.w = 0.0
            elif abs(sourceVector.y) < 0.6:
                norm = math.sqrt(1.0 - sourceVector.y * sourceVector.y)
                self.x = -sourceVector.z / norm
                self.y = 0.0
                self.z = sourceVector.x / norm
                self.w = 0.0
            else:
                norm = math.sqrt(1.0 - sourceVector.z * sourceVector.z)
                self.x = sourceVector.y / norm
                self.y = -sourceVector.x / norm
                self.z = 0.0
                self.w = 0.0
        else:
            s = math.sqrt(0.5 * dotProdPlus1)
            tmp = sourceVector.cross(targetVector) / (2.0 * s)
            self.x = tmp.x
            self.y = tmp.y
            self.z = tmp.z
            self.w = s

    def slerp(self, other, t):
        dot = self.x * other.x + self.y * other.y + self.z * other.z + self.w * other.w

        if dot < 0.0:
            other = Quat(-other.x, -other.y, -other.z, -other.w)
            dot = -dot

        if dot > 0.9995:
            result = Quat(
                self.x + t * (other.x - self.x),
                self.y + t * (other.y - self.y),
                self.z + t * (other.z - self.z),
                self.w + t * (other.w - self.w),
            ).normalize()
        else:
            theta_0 = math.acos(dot)
            theta = theta_0 * t
            sin_theta = math.sin(theta)
            sin_theta_0 = math.sin(theta_0)
            s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
            s1 = sin_theta / sin_theta_0
            result = Quat(
                s0 * self.x + s1 * other.x,
                s0 * self.y + s1 * other.y,
                s0 * self.z + s1 * other.z,
                s0 * self.w + s1 * other.w,
            )

        return result.normalize()

    def normalize(self):
        norm = math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z + self.w * self.w)
        if norm > 0:
            inv_norm = 1.0 / norm
            self.x *= inv_norm
            self.y *= inv_norm
            self.z *= inv_norm
            self.w *= inv_norm
        return self
