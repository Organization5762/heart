from __future__ import annotations

from typing import TYPE_CHECKING, Any

from heart.device import Device
from heart.navigation import AppController, ComposedRenderer
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import apply_provider_registrations
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.container.container import RuntimeContainer
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.rendering.pacing import RenderLoopPacer
from heart.runtime.rendering.pipeline import RendererVariant, RenderPipeline
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.runtime.game_loop import GameLoop
    from heart.runtime.game_loop.components import GameLoopComponents
    from heart.runtime.game_loop.event_handler import PygameEventHandler

ContainerOverrides = dict[type[Any], Any]


def build_runtime_container(
    *,
    device: Device,
    render_variant: RendererVariant,
    overrides: ContainerOverrides | None = None,
) -> RuntimeContainer:
    """Create a runtime container with the core services wired for a device."""

    container = RuntimeContainer()
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
    overrides: ContainerOverrides | None = None,
) -> None:
    """Register core bindings used by the runtime container."""

    resolved_overrides = overrides or {}
    configuration_registry = _resolve_override(
        resolved_overrides,
        ConfigurationRegistry,
        ConfigurationRegistry(),
    )
    peripheral_registry = _resolve_override(
        resolved_overrides,
        PeripheralConfigurationRegistry,
        PeripheralConfigurationRegistry(),
    )
    configuration_loader = _resolve_override(
        resolved_overrides,
        PeripheralConfigurationLoader,
        PeripheralConfigurationLoader(registry=peripheral_registry),
    )
    peripheral_manager = _resolve_override(
        resolved_overrides,
        PeripheralManager,
        PeripheralManager(configuration_loader=configuration_loader),
    )
    display_context = _resolve_override(
        resolved_overrides,
        DisplayContext,
        DisplayContext(device=device),
    )
    surface_provider = _resolve_override(
        resolved_overrides,
        RendererSurfaceProvider,
        RendererSurfaceProvider(display_context),
    )
    surface_provider._container = container
    render_pipeline = _resolve_override(
        resolved_overrides,
        RenderPipeline,
        RenderPipeline(
            display_context=display_context,
            peripheral_manager=peripheral_manager,
            render_variant=render_variant,
        ),
    )
    peripheral_runtime = _resolve_override(
        resolved_overrides,
        PeripheralRuntime,
        PeripheralRuntime(peripheral_manager),
    )
    render_loop_pacer = _resolve_override(
        resolved_overrides,
        RenderLoopPacer,
        RenderLoopPacer(
            strategy=Configuration.render_loop_pacing_strategy(),
            min_interval_ms=Configuration.render_loop_pacing_min_interval_ms(),
            utilization_target=Configuration.render_loop_pacing_utilization(),
        ),
    )
    app_controller = _resolve_override(
        resolved_overrides,
        AppController,
        AppController(renderer_resolver=container),
    )
    event_handler_type = _event_handler_type()
    event_handler = _resolve_override(
        resolved_overrides,
        event_handler_type,
        event_handler_type(),
    )
    game_loop_components_type = _game_loop_components_type()
    components = _resolve_override(
        resolved_overrides,
        game_loop_components_type,
        game_loop_components_type(
            app_controller=app_controller,
            display=display_context,
            render_pipeline=render_pipeline,
            event_handler=event_handler,
            peripheral_manager=peripheral_manager,
            peripheral_runtime=peripheral_runtime,
        ),
    )

    container.bind_instance(RuntimeContainer, container)
    container.bind_instance(Device, device)
    container.bind_instance(RendererVariant, render_variant)
    container.bind_instance(ConfigurationRegistry, configuration_registry)
    container.bind_instance(PeripheralConfigurationRegistry, peripheral_registry)
    container.bind_instance(PeripheralConfigurationLoader, configuration_loader)
    container.bind_instance(PeripheralManager, peripheral_manager)
    container.bind_instance(DisplayContext, display_context)
    container.bind_instance(RendererSurfaceProvider, surface_provider)
    container.bind_instance(RenderPipeline, render_pipeline)
    container.bind_instance(PeripheralRuntime, peripheral_runtime)
    container.bind_instance(RenderLoopPacer, render_loop_pacer)
    container.bind_instance(AppController, app_controller)
    container.bind_instance(event_handler_type, event_handler)
    container.bind_instance(game_loop_components_type, components)

    apply_provider_registrations(container)

    _bind_provider_if_missing(
        container,
        ComposedRenderer,
        lambda: ComposedRenderer(surface_provider=surface_provider),
    )
    _bind_provider_if_missing(
        container,
        _game_loop_type(),
        lambda: _build_game_loop(
            device=device,
            container=container,
            render_variant=render_variant,
        ),
    )


def _resolve_override(
    overrides: ContainerOverrides,
    key: type[Any],
    default: Any,
) -> Any:
    return overrides.get(key, default)


def _bind_provider_if_missing(
    container: RuntimeContainer,
    key: type[Any],
    provider: Any,
) -> None:
    if key in container.defined_types:
        return
    container[key] = provider


def _game_loop_type() -> type["GameLoop"]:
    from heart.runtime.game_loop import GameLoop

    return GameLoop


def _game_loop_components_type() -> type["GameLoopComponents"]:
    from heart.runtime.game_loop.components import GameLoopComponents

    return GameLoopComponents


def _event_handler_type() -> type["PygameEventHandler"]:
    from heart.runtime.game_loop.event_handler import PygameEventHandler

    return PygameEventHandler


def _build_game_loop(
    *,
    device: Device,
    container: RuntimeContainer,
    render_variant: RendererVariant,
) -> "GameLoop":
    from heart.runtime.game_loop import GameLoop

    return GameLoop(
        device=device,
        resolver=container,
        render_variant=render_variant,
    )
