"""Validate container-backed resolution for the combined BPM screen renderer."""

from heart.renderers.combined_bpm_screen import CombinedBpmScreen
from heart.runtime.container import build_runtime_container
from heart.runtime.rendering.variants import RendererVariant


class TestCombinedBpmScreenResolution:
    """Ensure CombinedBpmScreen resolves through the runtime container so configuration wiring stays usable."""

    def test_container_resolves_combined_bpm_screen(self, device) -> None:
        """Verify the runtime container can build CombinedBpmScreen so configuration-driven scene selection does not fail."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.ITERATIVE,
        )

        renderer = container.resolve(CombinedBpmScreen)

        assert isinstance(renderer, CombinedBpmScreen)
