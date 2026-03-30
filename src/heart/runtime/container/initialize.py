from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lagom import Container as RuntimeContainer
from lagom import Singleton

from heart.device import Device
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import apply_provider_registrations
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime

OverrideMap = Mapping[type[Any], Any]


def build_runtime_container(
    *,
    device: Device,
    overrides: OverrideMap | None = None,
) -> RuntimeContainer:
    """Create a runtime container with the core runtime bindings."""

    container = RuntimeContainer()
    configure_runtime_container(
        container,
        device=device,
        overrides=overrides,
    )
    return container


def configure_runtime_container(
    container: RuntimeContainer,
    *,
    device: Device,
    overrides: OverrideMap | None = None,
) -> None:
    """Register core runtime bindings on ``container`` without clobbering overrides."""

    override_keys = set(overrides or {})

    _define_default(container, RuntimeContainer, container, override_keys)
    _define_default(container, Device, device, override_keys)
    _define_default(
        container,
        PeripheralConfigurationRegistry,
        Singleton(PeripheralConfigurationRegistry),
        override_keys,
    )
    _define_default(
        container,
        PeripheralConfigurationLoader,
        Singleton(_build_peripheral_configuration_loader),
        override_keys,
    )
    _define_default(
        container, PeripheralManager, Singleton(_build_peripheral_manager), override_keys
    )
    _define_default(
        container, ConfigurationRegistry, Singleton(ConfigurationRegistry), override_keys
    )
    _define_default(container, DisplayContext, Singleton(DisplayContext), override_keys)
    _define_default(
        container, PeripheralRuntime, Singleton(PeripheralRuntime), override_keys
    )
    _define_default(
        container,
        _event_handler_type(),
        Singleton(_build_event_handler),
        override_keys,
    )
    _define_default(
        container,
        _game_modes_type(),
        Singleton(_build_game_modes),
        override_keys,
    )
    _define_default(
        container,
        _game_loop_components_type(),
        Singleton(_build_game_loop_components),
        override_keys,
    )
    _define_default(
        container, _composed_renderer_type(), _build_composed_renderer, override_keys
    )
    _define_default(container, _multi_scene_type(), _build_multi_scene, override_keys)

    if overrides:
        for key, value in overrides.items():
            container[key] = value

    apply_provider_registrations(container)
    _define_default(
        container, _game_loop_type(), Singleton(_build_game_loop), override_keys
    )


def _define_default(
    container: RuntimeContainer,
    key: type[Any],
    value: Any,
    override_keys: set[type[Any]],
) -> None:
    if key in override_keys:
        return
    if key not in container.defined_types:
        container[key] = value


def _build_peripheral_configuration_loader(
    container: RuntimeContainer,
) -> PeripheralConfigurationLoader:
    return PeripheralConfigurationLoader(
        registry=container.resolve(PeripheralConfigurationRegistry)
    )


def _build_peripheral_manager(
    container: RuntimeContainer,
) -> PeripheralManager:
    return PeripheralManager(
        configuration_loader=container.resolve(PeripheralConfigurationLoader)
    )
def _build_game_modes(container: RuntimeContainer) -> Any:
    GameModes = _game_modes_type()
    return GameModes(renderer_resolver=container)


def _build_game_loop_components(
    container: RuntimeContainer,
) -> Any:
    GameLoopComponents = _game_loop_components_type()
    return GameLoopComponents(
        game_modes=container.resolve(_game_modes_type()),
        display=container.resolve(DisplayContext),
        event_handler=container.resolve(_event_handler_type()),
        peripheral_manager=container.resolve(PeripheralManager),
        peripheral_runtime=container.resolve(PeripheralRuntime),
    )


def _build_event_handler() -> Any:
    return _event_handler_type()()


def _build_composed_renderer(container: RuntimeContainer) -> Any:
    ComposedRenderer = _composed_renderer_type()
    return ComposedRenderer([], renderer_resolver=container)


def _build_multi_scene(container: RuntimeContainer) -> Any:
    MultiScene = _multi_scene_type()
    return MultiScene([], renderer_resolver=container)


def _build_game_loop(
    container: RuntimeContainer,
) -> Any:
    game_loop_type = _game_loop_type()
    return game_loop_type(
        device=container.resolve(Device),
        resolver=container,
    )


def _game_loop_type():
    from heart.runtime.game_loop import GameLoop

    return GameLoop


def _game_modes_type():
    from heart.navigation import GameModes

    return GameModes


def _composed_renderer_type():
    from heart.navigation import ComposedRenderer

    return ComposedRenderer


def _multi_scene_type():
    from heart.navigation import MultiScene

    return MultiScene


def _game_loop_components_type():
    from heart.runtime.game_loop.components import GameLoopComponents

    return GameLoopComponents


def _event_handler_type():
    from heart.runtime.game_loop.event_handler import PygameEventHandler

    return PygameEventHandler
