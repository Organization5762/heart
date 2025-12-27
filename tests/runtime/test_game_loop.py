import pytest

from heart.runtime import game_loop as game_loop_module
from heart.runtime.container import build_runtime_container
from heart.runtime.game_loop import GameLoop
from heart.runtime.render_pipeline import RendererVariant


class TestGameLoopBehavior:
    """Cover core GameLoop invariants so the runtime loop stays predictable under orchestration."""

    def test_one_loop_requires_initialized_screen(self, device) -> None:
        """Confirm _one_loop rejects missing screens, preventing render passes before display setup for stability."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.ITERATIVE,
        )
        loop = GameLoop(device=device, resolver=container)

        with pytest.raises(RuntimeError, match="screen is not initialized"):
            loop._one_loop([])

    def test_set_singleton_preserves_existing_instance(
        self, device, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ensure the first GameLoop stays active, avoiding unexpected global swaps that could disrupt runtime state."""
        monkeypatch.setattr(game_loop_module, "ACTIVE_GAME_LOOP", None)
        primary = GameLoop(
            device=device,
            resolver=build_runtime_container(
                device=device,
                render_variant=RendererVariant.ITERATIVE,
            ),
        )
        primary._set_singleton()

        secondary = GameLoop(
            device=device,
            resolver=build_runtime_container(
                device=device,
                render_variant=RendererVariant.ITERATIVE,
            ),
        )
        secondary._set_singleton()

        assert GameLoop.get_game_loop() is primary
