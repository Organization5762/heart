import random
from dataclasses import dataclass
from typing import Iterator


@dataclass(slots=True, frozen=True)
class Color:
    r: int
    g: int
    b: int

    @staticmethod
    def kirby() -> "Color":
        return Color(r=255, g=105, b=180)

    def __post_init__(self) -> None:
        for variant in self._as_tuple():
            assert variant >= 0 and variant <= 255, (
                f"Expected all color values to be between 0 and 255. Found {self.rgb}"
            )

    def tuple(self) -> tuple[int, int, int]:
        return self._as_tuple()

    # todo (clem): why is this private anyway, re-exposed above
    def _as_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def __iter__(self) -> Iterator[int]:
        return iter(self._as_tuple())

    def __getitem__(self, index: int) -> int:
        return self._as_tuple()[index]

    @classmethod
    def random(cls) -> "Color":
        randbytes = random.getrandbits(24).to_bytes(3, "little")
        return Color(
            r=int(randbytes[0] / 2),
            g=int(randbytes[1] / 2),
            b=int(randbytes[2] / 2),
        )

    def dim(self, fraction: float) -> "Color":
        return Color(
            r=self.__clamp_rgb(self.r * (1 - fraction)),
            g=self.__clamp_rgb(self.g * (1 - fraction)),
            b=self.__clamp_rgb(self.b * (1 - fraction)),
        )

    def __clamp(self, min_value: int, max_value: int, value: float) -> int:
        clamped = min(max_value, max(min_value, int(round(value))))
        return clamped

    def __clamp_rgb(self, value: float) -> int:
        return self.__clamp(0, 255, value)
