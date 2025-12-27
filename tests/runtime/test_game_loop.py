import pytest

from heart.runtime.game_loop import GameLoop


class TestGameLoop:
    """Exercise core GameLoop guardrails so lifecycle assumptions stay reliable for runtime orchestration."""

    def test_singleton_preserves_first_instance(
        self,
        device,
        resolver,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure the first GameLoop remains active so global access stays predictable during runtime setup."""
        monkeypatch.setattr("heart.runtime.game_loop.ACTIVE_GAME_LOOP", None)

        first_loop = GameLoop(device=device, resolver=resolver)
        second_loop = GameLoop(device=device, resolver=resolver)

        first_loop._set_singleton()
        second_loop._set_singleton()

        assert GameLoop.get_game_loop() is first_loop

    def test_one_loop_requires_initialized_screen(self, device, resolver) -> None:
        """Confirm _one_loop refuses to run without a screen so rendering doesn't fail silently in production."""
        loop = GameLoop(device=device, resolver=resolver)

        with pytest.raises(RuntimeError, match="GameLoop screen is not initialized"):
            loop._one_loop([])
