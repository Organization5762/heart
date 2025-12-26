from __future__ import annotations

from typing import Any, Mapping

from lagom import Container, Singleton

from heart.device import Device
from heart.navigation import AppController
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import apply_provider_registrations
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.display_context import DisplayContext
from heart.runtime.frame_presenter import FramePresenter
from heart.runtime.game_loop_components import GameLoopComponents
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.pygame_event_handler import PygameEventHandler
from heart.runtime.render_pipeline import RendererVariant, RenderPipeline
from heart.utilities.logging import get_logger

RuntimeContainer = Container

logger = get_logger(__name__)


def build_runtime_container(
    device: Device,
    render_variant: RendererVariant,
    overrides: Mapping[type[Any], object] | None = None,
) -> RuntimeContainer:
    container = Container()
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
        Singleton(
            lambda resolver: PeripheralConfigurationLoader(
                registry=resolver[PeripheralConfigurationRegistry]
            )
        ),
    )
    _bind(
        container,
        overrides,
        PeripheralManager,
        Singleton(
            lambda resolver: PeripheralManager(
                configuration_loader=resolver[PeripheralConfigurationLoader]
            )
        ),
    )
    _bind(
        container,
        overrides,
        DisplayContext,
        Singleton(lambda resolver: DisplayContext(device=resolver[Device])),
    )
    _bind(
        container,
        overrides,
        RenderPipeline,
        Singleton(
            lambda resolver: RenderPipeline(
                device=resolver[Device],
                peripheral_manager=resolver[PeripheralManager],
                render_variant=resolver[RendererVariant],
            )
        ),
    )
    _bind(
        container,
        overrides,
        FramePresenter,
        Singleton(
            lambda resolver: FramePresenter(
                device=resolver[Device],
                display=resolver[DisplayContext],
                render_pipeline=resolver[RenderPipeline],
            )
        ),
    )
    _bind(
        container,
        overrides,
        PeripheralRuntime,
        Singleton(lambda resolver: PeripheralRuntime(resolver[PeripheralManager])),
    )
    _bind(
        container,
        overrides,
        AppController,
        Singleton(lambda resolver: AppController(renderer_resolver=resolver)),
    )
    _bind(
        container,
        overrides,
        ConfigurationRegistry,
        Singleton(ConfigurationRegistry),
    )
    _bind(
        container,
        overrides,
        GameLoopComponents,
        Singleton(
            lambda resolver: GameLoopComponents(
                app_controller=resolver[AppController],
                display=resolver[DisplayContext],
                render_pipeline=resolver[RenderPipeline],
                frame_presenter=resolver[FramePresenter],
                event_handler=resolver[PygameEventHandler],
                peripheral_manager=resolver[PeripheralManager],
                peripheral_runtime=resolver[PeripheralRuntime],
            )
        ),
    )
    _bind(container, overrides, PygameEventHandler, Singleton(PygameEventHandler))
    from heart.runtime.game_loop import GameLoop

    _bind(
        container,
        overrides,
        GameLoop,
        Singleton(
            lambda resolver: GameLoop(
                device=resolver[Device],
                resolver=resolver,
                render_variant=resolver[RendererVariant],
            )
        ),
    )
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
