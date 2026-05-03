from abc import abstractmethod
from typing import Generic, TypeVar

import heart.utilities.reactive as reactive
from heart.peripheral.core import InputDescriptor
from heart.peripheral.core.providers import registry as providers_registry
from heart.utilities.reactive_threads import pipe_in_background

apply_provider_registrations = providers_registry.apply_provider_registrations
register_provider = providers_registry.register_provider
register_singleton_provider = providers_registry.register_singleton_provider
registered_providers = providers_registry.registered_providers

T = TypeVar("T")


class ObservableProvider(Generic[T]):
    @abstractmethod
    def observable(
        self, *args: object, **kwargs: object
    ) -> reactive.Observable[T]:
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

    def observable(
        self, *args: object, **kwargs: object
    ) -> reactive.Observable[T]:
        return pipe_in_background(
            reactive.just(self._state),
            reactive.operators.share(),
        )
