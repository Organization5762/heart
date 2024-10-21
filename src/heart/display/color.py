import random
from dataclasses import dataclass
from typing import Iterator


@dataclass(slots=True, frozen=True)
class Color:
    r: int
    g: int
    b: int

    def __post_init__(self):
        for variant in self._as_tuple():
            assert (
                variant >= 0 and variant <= 255
            ), f"Expected all color values to be between 0 and 255. Found {self.rgb}"

    def _as_tuple(self):
        return (self.r, self.g, self.b)

    def __iter__(self) -> Iterator[int]:
        return iter(self._as_tuple())

    def __getitem__(self, index: int) -> int:
        return self._as_tuple()[index]

    @classmethod
    def random(cls) -> "Color":
        randbytes = random.getrandbits(24).to_bytes(3, "little")
        return Color(
            r=randbytes[0] * 0.5,
            g=randbytes[1] * 0.5,
            b=randbytes[2] * 0.5,
        )

    def dim(self, fraction: float) -> "Color":
        return Color(
            r=self.__clamp_rgb(self.r - (self.r * fraction)),
            g=self.__clamp_rgb(self.g - (self.g * fraction)),
            b=self.__clamp_rgb(self.b - (self.b * fraction)),
        )

    def __clamp(self, min_value: int, max_value: int, value: int) -> int:
        return min(max(value, min_value), max_value)

    def __clamp_rgb(self, value: int) -> int:
        return self.__clamp(0, 255, value)
