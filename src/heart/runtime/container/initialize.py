from __future__ import annotations

from typing import cast

from heart.firmware.environment import FirmwareEnvironment
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import apply_provider_registrations
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.container import RuntimeContainer
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.rendering.pacing import RenderLoopPacer


def build_runtime_container(
    firmware_environment: FirmwareEnvironment | None = None,
) -> RuntimeContainer:
    """Create a runtime container with expected core bindings."""

    container = RuntimeContainer()
    configure_runtime_container(container, firmware_environment=firmware_environment)
    return container


def configure_runtime_container(
    container: RuntimeContainer,
    firmware_environment: FirmwareEnvironment | None = None,
) -> None:
    """Register core bindings used by the runtime container."""

    if firmware_environment is None:
        firmware_environment = FirmwareEnvironment.from_env()

    peripheral_registry = PeripheralConfigurationRegistry.from_env()
    configuration_registry = ConfigurationRegistry.from_env()
    peripheral_manager = PeripheralManager.from_registry(peripheral_registry)
    display_context = DisplayContext(
        firmware_environment=firmware_environment,
        peripheral_manager=peripheral_manager,
    )
    render_loop_pacer = RenderLoopPacer.from_env()
    container.bind_instance(FirmwareEnvironment, firmware_environment)
    container.bind_instance(PeripheralConfigurationRegistry, peripheral_registry)
    container.bind_instance(ConfigurationRegistry, configuration_registry)
    container.bind_instance(PeripheralManager, peripheral_manager)
    container.bind_instance(DisplayContext, display_context)
    container.bind_instance(PeripheralRuntime, PeripheralRuntime(peripheral_manager))
    container.bind_instance(RenderLoopPacer, render_loop_pacer)

    apply_provider_registrations(container)

    container.bind_instance(RuntimeContainer, container)

    if firmware_environment.is_isolated:
        container.bind_instance(
            RuntimeContainer,
            cast(RuntimeContainer, container.reconfigure()),
        )
