import abc
from dataclasses import dataclass
from typing import Any, Iterator, Self

@dataclass
class Input:
    event_type: str
    data: Any
    producer_id: int = 0


class Peripheral(abc.ABC):
    def run(self) -> None:
        pass

    @staticmethod
    def detect() -> Iterator[Self]:
        raise NotImplementedError("'detect' is not implemented")

    def handle_input(self, input: Input) -> None:
        pass

    def update_due_to_data(self, data: dict) -> None:
        i = Input(**data)
        self.handle_input(i)
