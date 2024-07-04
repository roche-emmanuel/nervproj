"""Simple Vec4 class"""

from nvp.math.vec3 import Vec3


class Vec4:
    """Vec4 class"""

    def __init__(self, x: float, y: float, z: float, w: float):
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
            raise IndexError("Vec4 index out of range")

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
            raise IndexError("Vec4 index out of range")

    def set(self, *args):
        """Set this quat"""
        if len(args) == 1 and isinstance(args[0], Vec4):
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

    def __neg__(self):
        return Vec4(-self.x, -self.y, -self.z, -self.w)

    def __mul__(self, other) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z + self.w * other.w

    def __str__(self) -> str:
        return f"Vec4({self.x}, {self.y}, {self.z}, {self.w})"

    def xyz(self):
        """Retrieve the sub vec3"""
        return Vec3(self.x, self.y, self.z)
