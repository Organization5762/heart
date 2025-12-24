from abc import abstractmethod
from typing import Generic, TypeVar

import reactivex
from lagom import Container
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager

T = TypeVar("T")

class ObservableProvider(Generic[T]):
    @abstractmethod
    def observable(self) -> reactivex.Observable[T]:
        raise NotImplementedError("")


class FixedStateProvider(ObservableProvider[T]):
    def __init__(self, state: T) -> None:
        self._state = state

    @property
    def state(self) -> T:
        return self._state

    def observable(self) -> reactivex.Observable[T]:
        return reactivex.just(self._state).pipe(ops.share())

container = Container()
container[PeripheralManager] = PeripheralManager()
