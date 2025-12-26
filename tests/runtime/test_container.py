from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.game_loop import GameLoop
from heart.runtime.game_loop_components import GameLoopComponents
from heart.runtime.render_pipeline import RendererVariant, RenderPipeline


class TestRuntimeContainer:
    """Validate runtime container wiring so core services resolve consistently across the loop lifecycle."""

    def test_container_build_registers_core_singletons(self, device) -> None:
        """Verify that the runtime container wires core singletons, ensuring consistent service reuse across frames."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.BINARY,
        )

        render_pipeline = container.resolve(RenderPipeline)

        assert container.resolve(PeripheralManager) is container.resolve(
            PeripheralManager
        )
        assert container.resolve(DisplayContext) is container.resolve(DisplayContext)
        assert render_pipeline is container.resolve(RenderPipeline)
        assert render_pipeline.renderer_variant is RendererVariant.BINARY

    def test_container_injects_configuration_registry(self, device) -> None:
        """Confirm the container shares a registry instance so configuration overrides stay consistent at runtime."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.BINARY,
        )

        registry = container.resolve(PeripheralConfigurationRegistry)
        manager = container.resolve(PeripheralManager)

        assert manager.configuration_registry is registry

    def test_game_loop_uses_container_overrides(self, device) -> None:
        """Ensure GameLoop honors container overrides so tests can swap implementations without touching runtime code."""
        stub_manager = PeripheralManager()
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.ITERATIVE,
            overrides={PeripheralManager: stub_manager},
        )
        loop = GameLoop(device=device, resolver=container)

        assert loop.peripheral_manager is stub_manager

    def test_container_resolves_game_loop_components(self, device) -> None:
        """Confirm GameLoopComponents resolve from the container so runtime services stay centrally wired."""
        stub_manager = PeripheralManager()
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.BINARY,
            overrides={PeripheralManager: stub_manager},
        )

        components = container.resolve(GameLoopComponents)

        assert components.peripheral_manager is stub_manager
        assert components.render_pipeline.renderer_variant is RendererVariant.BINARY

    def test_game_loop_prefers_container_device(self, device) -> None:
        """Verify the GameLoop uses the container-provided Device so overrides remain consistent across services."""
        alternate_device = type(device)(orientation=device.orientation)
        container = build_runtime_container(
            device=alternate_device,
            render_variant=RendererVariant.BINARY,
        )

        loop = GameLoop(device=device, resolver=container)

        assert loop.device is alternate_device
