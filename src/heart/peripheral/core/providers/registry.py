from __future__ import annotations

from typing import Any

from lagom import Container

ProviderKey = type[Any]
ProviderValue = Any

_registry: dict[ProviderKey, ProviderValue] = {}
_containers: list[Container] = []


def register_provider(key: ProviderKey, provider: ProviderValue) -> None:
    _registry[key] = provider
    for container in _containers:
        _register_container_provider(container, key, provider)


def apply_provider_registrations(container: Container) -> None:
    for key, provider in _registry.items():
        _register_container_provider(container, key, provider)
    if container not in _containers:
        _containers.append(container)


def registered_providers() -> dict[ProviderKey, ProviderValue]:
    return dict(_registry)


def _register_container_provider(
    container: Container,
    key: ProviderKey,
    provider: ProviderValue,
) -> None:
    if key in container.defined_types:
        return
    container[key] = provider
