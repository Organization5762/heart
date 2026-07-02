from abc import abstractmethod
from typing import Generic, TypeVar

from manyfold import ConstantNode

from heart.peripheral.core import InputDescriptor
from heart.peripheral.core.providers import registry as providers_registry
from heart.peripheral.core.variables import Variable

apply_provider_registrations = providers_registry.apply_provider_registrations
register_provider = providers_registry.register_provider
register_singleton_provider = providers_registry.register_singleton_provider
registered_providers = providers_registry.registered_providers
T = TypeVar("T")


class ObservableProvider(Generic[T]):
    @abstractmethod
    def observable(self, *args: object, **kwargs: object) -> Variable[T]:
        raise NotImplementedError("")

    def inputs(self) -> tuple[InputDescriptor, ...]:
        """Declare the input streams this provider consumes."""
        return ()


class StaticStateProvider(ObservableProvider[T]):
    def __init__(self, state: T) -> None:
        self._state = state

    @property
    def state(self) -> T:
        return self._state

    def observable(self, *args: object, **kwargs: object) -> Variable[T]:
        return ConstantNode(self._state).observable()
