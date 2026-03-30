from heart.navigation import GameModes
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.game_loop import GameLoop
from heart.runtime.game_loop.components import GameLoopComponents


class TestRuntimeContainer:
    """Validate runtime container wiring so core services resolve consistently across the loop lifecycle."""

    def test_container_build_registers_core_singletons(self, device) -> None:
        """Verify that the runtime container wires core singletons, ensuring consistent service reuse across frames."""
        container = build_runtime_container(device=device)

        assert container.resolve(PeripheralManager) is container.resolve(
            PeripheralManager
        )
        assert container.resolve(DisplayContext) is container.resolve(DisplayContext)
        assert container.resolve(GameModes) is container.resolve(GameModes)
        assert container.resolve(RandomnessProvider) is container.resolve(
            RandomnessProvider
        )

    def test_container_injects_configuration_registry(self, device) -> None:
        """Confirm the container shares a registry instance so configuration overrides stay consistent at runtime."""
        container = build_runtime_container(device=device)

        registry = container.resolve(PeripheralConfigurationRegistry)
        manager = container.resolve(PeripheralManager)

        assert manager.configuration_registry is registry

    def test_container_allows_configuration_loader_overrides(self, device) -> None:
        """Ensure configuration loader overrides propagate, so tests can inject loader behavior cleanly."""
        registry = PeripheralConfigurationRegistry()
        loader = PeripheralConfigurationLoader(
            configuration="test-override",
            registry=registry,
        )
        container = build_runtime_container(
            device=device,
            overrides={PeripheralConfigurationLoader: loader},
        )

        manager = container.resolve(PeripheralManager)

        assert manager.configuration_loader is loader

    def test_game_loop_uses_container_overrides(self, device) -> None:
        """Ensure GameLoop honors container overrides so tests can swap implementations without touching runtime code."""
        stub_manager = PeripheralManager()
        container = build_runtime_container(
            device=device,
            overrides={PeripheralManager: stub_manager},
        )
        loop = GameLoop(device=device, resolver=container)

        assert loop.peripheral_manager is stub_manager

    def test_container_resolves_game_loop_components(self, device) -> None:
        """Confirm GameLoopComponents resolve from the container so runtime services stay centrally wired."""
        stub_manager = PeripheralManager()
        container = build_runtime_container(
            device=device,
            overrides={PeripheralManager: stub_manager},
        )

        components = container.resolve(GameLoopComponents)

        assert components.peripheral_manager is stub_manager
        assert components.game_modes is container.resolve(GameModes)

    def test_game_loop_prefers_container_device(self, device) -> None:
        """Verify the GameLoop uses the container-provided Device so overrides remain consistent across services."""
        alternate_device = type(device)(orientation=device.orientation)
        container = build_runtime_container(device=alternate_device)

        loop = GameLoop(device=device, resolver=container)

        assert loop.device is alternate_device

    def test_container_resolves_game_loop(self, device) -> None:
        """Confirm the container can resolve GameLoop so entrypoints reuse the shared DI wiring."""
        container = build_runtime_container(device=device)

        loop = container.resolve(GameLoop)

        assert loop.context_container is container
        assert loop.device is device
