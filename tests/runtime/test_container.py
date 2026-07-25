from heart.navigation import GameModes
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.game_loop import GameLoop


class TestRuntimeContainer:
    def test_container_resolves_one_shared_runtime_graph(self, device) -> None:
        container = build_runtime_container(device=device)

        loop = container.resolve(GameLoop)
        manager = container.resolve(PeripheralManager)

        assert loop.context_container is container
        assert loop.device is device
        assert loop.peripheral_manager is manager
        assert manager.configuration_registry is container.resolve(
            PeripheralConfigurationRegistry
        )
        for service in (
            PeripheralManager,
            DisplayContext,
            GameModes,
            RandomnessProvider,
        ):
            assert container.resolve(service) is container.resolve(service)

    def test_container_overrides_reach_the_resolved_game_loop(self, device) -> None:
        registry = PeripheralConfigurationRegistry()
        loader = PeripheralConfigurationLoader(
            configuration="test-override",
            registry=registry,
        )
        manager = PeripheralManager(configuration_loader=loader)
        alternate_device = type(device)(orientation=device.orientation)
        container = build_runtime_container(
            device=alternate_device,
            overrides={
                PeripheralConfigurationLoader: loader,
                PeripheralManager: manager,
            },
        )

        loop = container.resolve(GameLoop)

        assert loop.device is alternate_device
        assert loop.peripheral_manager is manager
        assert manager.configuration_loader is loader
