from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.game_loop import GameLoop
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
