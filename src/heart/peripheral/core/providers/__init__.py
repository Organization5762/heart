from abc import abstractmethod
from typing import Generic, TypeVar

from manyfold import ConstantNode, Subscribable

from heart.peripheral.core.providers import registry as providers_registry

apply_provider_registrations = providers_registry.apply_provider_registrations
register_provider = providers_registry.register_provider
register_singleton_provider = providers_registry.register_singleton_provider
registered_providers = providers_registry.registered_providers
T = TypeVar("T")


class StateProvider(Generic[T]):
    @abstractmethod
    def states(self, *args: object, **kwargs: object) -> Subscribable[T]:
        raise NotImplementedError("")


class ConstantStateProvider(StateProvider[T]):
    def __init__(self, state: T) -> None:
        self._state = state

    @property
    def state(self) -> T:
        return self._state

    def states(self, *args: object, **kwargs: object) -> Subscribable[T]:
        return ConstantNode(self._state).observable()
