import abc
from typing import Iterator, Self

class Peripherial(abc.ABC):
    def run(self) -> None:
        pass

    @staticmethod
    def detect() -> Iterator[Self]:
        raise NotImplementedError("'detect' is not implemented")