from abc import abstractmethod
from typing import Generic, TypeVar

import reactivex
from lagom import Container

from heart.peripheral.core.manager import PeripheralManager

T = TypeVar("T")

class ObservableProvider(Generic[T]):
    @abstractmethod
    def observable(self) -> reactivex.Observable[T]:
        raise NotImplementedError("")

container = Container()
container[PeripheralManager] = PeripheralManager()