import abc
from dataclasses import dataclass
from typing import Any, Iterator, Self

import pygame

@dataclass
class Input:
    event_type: str
    data: Any

class NotificationBus():
    def with_event_emit():


class Peripheral(abc.ABC):
    def __init__(self) -> None:
        super().__init__()

    def run(self) -> None:
        pass

    @staticmethod
    def detect() -> Iterator[Self]:
        raise NotImplementedError("'detect' is not implemented")

    def handle_input(self, input: Input) -> None:
        pygame.event.post()
        pass

    def update_due_to_data(self, data: dict) -> None:
        i = Input(**data)
        self.handle_input(i)
