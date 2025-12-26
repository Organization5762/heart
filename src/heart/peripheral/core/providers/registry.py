from __future__ import annotations

import weakref
from typing import Any

from lagom import Container, Singleton

from heart.utilities.logging import get_logger

ProviderKey = type[Any]
ProviderValue = Any

_registry: dict[ProviderKey, ProviderValue] = {}
_containers: weakref.WeakSet[Container] = weakref.WeakSet()
logger = get_logger(__name__)


def register_provider(key: ProviderKey, provider: ProviderValue) -> None:
    _registry[key] = provider
    logger.debug("Registered Lagom provider for %s.", key)
    for container in _containers:
        _register_container_provider(container, key, provider)


def register_singleton_provider(
    key: ProviderKey, provider: ProviderValue
) -> None:
    register_provider(key, Singleton(provider))


def apply_provider_registrations(container: Container) -> None:
    logger.debug(
        "Applying Lagom provider registrations to container with %d entries.",
        len(_registry),
    )
    for key, provider in _registry.items():
        _register_container_provider(container, key, provider)
    _containers.add(container)


def registered_providers() -> dict[ProviderKey, ProviderValue]:
    return dict(_registry)


def _register_container_provider(
    container: Container,
    key: ProviderKey,
    provider: ProviderValue,
) -> None:
    if key in container.defined_types:
        logger.debug("Lagom container already defines %s; skipping.", key)
        return
    container[key] = provider
    logger.debug("Lagom container bound provider for %s.", key)
