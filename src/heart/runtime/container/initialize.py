from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from lagom import Singleton

from heart.device import Device
from heart.navigation import AppController
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import apply_provider_registrations
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.container import RuntimeContainer, container
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.rendering.pacing import RenderLoopPacer
from heart.runtime.rendering.pipeline import RendererVariant, RenderPipeline
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from heart.runtime.game_loop import GameLoop
    from heart.runtime.game_loop.components import GameLoopComponents


def _build_peripheral_configuration_loader(
    resolver: RuntimeContainer,
) -> PeripheralConfigurationLoader:
    return PeripheralConfigurationLoader(
        registry=resolver[PeripheralConfigurationRegistry]
    )


def _build_peripheral_manager(
    resolver: RuntimeContainer,
) -> PeripheralManager:
    return PeripheralManager(
        configuration_loader=resolver[PeripheralConfigurationLoader]
    )


def _build_display_context(resolver: RuntimeContainer) -> DisplayContext:
    return DisplayContext(device=resolver[Device])


def _build_render_pipeline(resolver: RuntimeContainer) -> RenderPipeline:
    return RenderPipeline(
        display_context=resolver[DisplayContext],
        peripheral_manager=resolver[PeripheralManager],
        render_variant=resolver[RendererVariant],
    )


def _build_peripheral_runtime(resolver: RuntimeContainer) -> PeripheralRuntime:
    return PeripheralRuntime(resolver[PeripheralManager])


def _build_app_controller() -> AppController:
    return AppController()


def _build_render_loop_pacer(_: RuntimeContainer) -> RenderLoopPacer:
    return RenderLoopPacer(
        strategy=Configuration.render_loop_pacing_strategy(),
        min_interval_ms=Configuration.render_loop_pacing_min_interval_ms(),
        utilization_target=Configuration.render_loop_pacing_utilization(),
    )


def _build_game_loop_components(
    resolver: RuntimeContainer,
) -> GameLoopComponents:
    from heart.runtime.game_loop.components import GameLoopComponents
    from heart.runtime.game_loop.event_handler import PygameEventHandler

    return GameLoopComponents(
        app_controller=resolver[AppController],
        display=resolver[DisplayContext],
        render_pipeline=resolver[RenderPipeline],
        event_handler=resolver[PygameEventHandler],
        peripheral_manager=resolver[PeripheralManager],
        peripheral_runtime=resolver[PeripheralRuntime],
    )


def _build_game_loop(resolver: RuntimeContainer) -> GameLoop:
    from heart.runtime.game_loop import GameLoop

    return GameLoop(
        device=resolver[Device],
        resolver=resolver,
        render_variant=resolver[RendererVariant],
    )


def build_runtime_container(
    device: Device,
    render_variant: RendererVariant,
    overrides: Mapping[type[Any], object] | None = None,
) -> RuntimeContainer:
    logger.debug("Created Lagom container for runtime configuration.")
    configure_runtime_container(
        container=container,
        device=device,
        render_variant=render_variant,
        overrides=overrides,
    )
    return container


def configure_runtime_container(
    *,
    container: RuntimeContainer,
    device: Device,
    render_variant: RendererVariant,
    overrides: Mapping[type[Any], object] | None = None,
) -> None:
    logger.debug(
        "Configuring Lagom runtime container with overrides=%s.",
        set(overrides.keys()) if overrides else set(),
    )
    _bind(container, overrides, Device, device)
    _bind(container, overrides, RendererVariant, render_variant)
    _configure_peripheral_bindings(container, overrides)
    _configure_display_bindings(container, overrides)
    _configure_render_bindings(container, overrides)
    _configure_runtime_bindings(container, overrides)
    _configure_game_loop_bindings(container, overrides)
    apply_provider_registrations(container)


def _bind(
    container: RuntimeContainer,
    overrides: Mapping[type[Any], object] | None,
    key: type[Any],
    value: object,
) -> None:
    if overrides and key in overrides:
        container[key] = overrides[key]
        logger.debug("Applied Lagom override for %s.", key)
        return
    if key in container.defined_types:
        logger.debug("Lagom already defined %s; skipping registration.", key)
        return
    container[key] = value
    logger.debug("Registered Lagom provider for %s.", key)


def _configure_peripheral_bindings(
    container: RuntimeContainer,
    overrides: Mapping[type[Any], object] | None,
) -> None:
    _bind(
        container,
        overrides,
        PeripheralConfigurationRegistry,
        Singleton(PeripheralConfigurationRegistry),
    )
    _bind(
        container,
        overrides,
        PeripheralConfigurationLoader,
        Singleton(_build_peripheral_configuration_loader),
    )
    _bind(
        container,
        overrides,
        PeripheralManager,
        Singleton(_build_peripheral_manager),
    )


def _configure_display_bindings(
    container: RuntimeContainer,
    overrides: Mapping[type[Any], object] | None,
) -> None:
    _bind(
        container,
        overrides,
        DisplayContext,
        Singleton(_build_display_context),
    )


def _configure_render_bindings(
    container: RuntimeContainer,
    overrides: Mapping[type[Any], object] | None,
) -> None:
    _bind(
        container,
        overrides,
        RenderPipeline,
        Singleton(_build_render_pipeline),
    )


def _configure_runtime_bindings(
    container: RuntimeContainer,
    overrides: Mapping[type[Any], object] | None,
) -> None:
    from heart.runtime.game_loop.event_handler import PygameEventHandler
    _bind(
        container,
        overrides,
        PeripheralRuntime,
        Singleton(_build_peripheral_runtime),
    )
    _bind(
        container,
        overrides,
        AppController,
        Singleton(_build_app_controller),
    )
    _bind(
        container,
        overrides,
        RenderLoopPacer,
        Singleton(_build_render_loop_pacer),
    )
    _bind(
        container,
        overrides,
        ConfigurationRegistry,
        Singleton(ConfigurationRegistry),
    )
    _bind(container, overrides, PygameEventHandler, Singleton(PygameEventHandler))


def _configure_game_loop_bindings(
    container: RuntimeContainer,
    overrides: Mapping[type[Any], object] | None,
) -> None:
    from heart.runtime.game_loop.components import GameLoopComponents
    _bind(
        container,
        overrides,
        GameLoopComponents,
        Singleton(_build_game_loop_components),
    )
    from heart.runtime.game_loop import GameLoop

    _bind(
        container,
        overrides,
        GameLoop,
        Singleton(_build_game_loop),
    )
