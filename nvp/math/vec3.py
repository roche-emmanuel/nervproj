"""Simple definition of a Vec3 class"""

import math


class Vec3:
    """Vec3 class"""

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

    def __getitem__(self, i: int) -> float:
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        elif i == 2:
            return self.z
        else:
            raise IndexError("Quat index out of range")

    def __setitem__(self, i: int, value: float) -> None:
        if i == 0:
            self.x = value
        elif i == 1:
            self.y = value
        elif i == 2:
            self.z = value
        else:
            raise IndexError("Quat index out of range")

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def __sub__(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __truediv__(self, scalar):
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def set(self, *args):
        """Set this vec3"""
        if len(args) == 1 and isinstance(args[0], Vec3):
            self.x = args[0].x
            self.y = args[0].y
            self.z = args[0].z
        elif len(args) == 3:
            self.x = args[0]
            self.y = args[1]
            self.z = args[2]
        else:
            raise ValueError("Invalid arguments for set")

    def dot(self, other):
        """dot operation"""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        """cross operation"""
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def clone(self):
        """Make a copy of this vector"""
        return Vec3(self.x, self.y, self.z)

    def length2(self):
        """Get length2 of vector"""
        return self.x**2 + self.y**2 + self.z**2

    def length(self):
        """Get length of vector"""
        return math.sqrt(self.length2())

    def normalize(self):
        """Normalize this vector"""
        mag = self.length()
        if mag == 0:
            return Vec3()
        self.set(self / mag)
        return mag

    def normalized(self):
        """Return a normalized copy of this vector"""
        vec = self.clone()
        vec.normalize()
        return vec

    def __repr__(self):
        return f"Vec3({self.x}, {self.y}, {self.z})"


# Define the static variables after the class definition
Vec3.X_AXIS = Vec3(1.0, 0.0, 0.0)
Vec3.Y_AXIS = Vec3(0.0, 1.0, 0.0)
Vec3.Z_AXIS = Vec3(0.0, 0.0, 1.0)
