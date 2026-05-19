from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from heart.device import Orientation
from heart.navigation.composed_renderer import ComposedRenderer
from heart.navigation.game_modes import GameModes
from heart.navigation.multi_scene import MultiScene
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.text import TextRendering
from heart.renderers.title_screen import TitleScreen
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class TotemDebugCyclePhase(StrEnum):
    TITLE = "title"
    SCENE = "scene"


@dataclass
class TotemDebugCycleState:
    phase: TotemDebugCyclePhase
    mode_index: int
    scene_index: int
    last_transition_monotonic: float


class TotemDebugCycle(StatefulBaseRenderer[TotemDebugCycleState]):
    def __init__(
        self,
        game_modes: GameModes,
        *,
        interval_seconds: float = 5.0,
        start_mode: int | str | None = None,
    ) -> None:
        super().__init__()
        self.game_modes = game_modes
        self.interval_seconds = max(0.1, interval_seconds)
        self.start_mode = start_mode

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> TotemDebugCycleState:
        del window, peripheral_manager, orientation
        mode_index = self._resolve_start_mode_index()
        self._show_title(mode_index)
        return TotemDebugCycleState(
            phase=TotemDebugCyclePhase.TITLE,
            mode_index=mode_index,
            scene_index=0,
            last_transition_monotonic=time.monotonic(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del window, orientation
        now = time.monotonic()
        if now - self.state.last_transition_monotonic < self.interval_seconds:
            return
        if self.state.phase is TotemDebugCyclePhase.TITLE:
            self._enter_mode(now)
        else:
            self._advance_or_exit_mode(now)

    def _enter_mode(self, now: float) -> None:
        logger.info(
            "totem_debug_cycle.enter_mode mode_index=%s mode=%s",
            self.state.mode_index,
            self._mode_name(self.state.mode_index),
        )
        self._show_mode(self.state.mode_index)
        self.update_state(
            phase=TotemDebugCyclePhase.SCENE,
            scene_index=0,
            last_transition_monotonic=now,
        )

    def _advance_or_exit_mode(self, now: float) -> None:
        multi_scene = self._active_multi_scene()
        scene_count = len(multi_scene.scenes) if multi_scene is not None else 1
        next_scene_index = self.state.scene_index + 1
        if multi_scene is not None and next_scene_index < scene_count:
            multi_scene.state.current_button_value += 1
            logger.info(
                "totem_debug_cycle.advance_scene mode_index=%s mode=%s scene_index=%s scene_count=%s",
                self.state.mode_index,
                self._mode_name(self.state.mode_index),
                next_scene_index,
                scene_count,
            )
            self.update_state(
                scene_index=next_scene_index,
                last_transition_monotonic=now,
            )
            return

        next_mode_index = self._next_mode_index(self.state.mode_index)
        logger.info(
            "totem_debug_cycle.exit_mode mode_index=%s mode=%s next_mode_index=%s next_mode=%s",
            self.state.mode_index,
            self._mode_name(self.state.mode_index),
            next_mode_index,
            self._mode_name(next_mode_index),
        )
        self._show_title(next_mode_index)
        self.update_state(
            phase=TotemDebugCyclePhase.TITLE,
            mode_index=next_mode_index,
            scene_index=0,
            last_transition_monotonic=now,
        )

    def _show_title(self, mode_index: int) -> None:
        state = self.game_modes.state
        state._reset_sliding_transition()
        state._active_mode_index = mode_index
        state.previous_mode_index = mode_index
        state.mode_offset = 0
        state.in_select_mode = True

    def _show_mode(self, mode_index: int) -> None:
        state = self.game_modes.state
        state._reset_sliding_transition()
        state._active_mode_index = mode_index
        state.previous_mode_index = mode_index
        state.mode_offset = 0
        state.in_select_mode = False
        self._reset_active_multi_scene()

    def _active_mode_index(self) -> int:
        entry_count = len(self.game_modes.state.entries)
        if entry_count == 0:
            return 0
        return self.game_modes.state._active_mode_index % entry_count

    def _resolve_start_mode_index(self) -> int:
        entry_count = len(self.game_modes.state.entries)
        if entry_count == 0:
            return 0
        if self.start_mode is None:
            return self._active_mode_index()
        if isinstance(self.start_mode, int):
            return self.start_mode % entry_count

        normalized_start = self.start_mode.strip().lower()
        if normalized_start == "":
            return self._active_mode_index()
        try:
            return int(normalized_start) % entry_count
        except ValueError:
            pass

        for index, entry in enumerate(self.game_modes.state.entries):
            haystack = self._mode_search_text(entry.title_renderer).lower()
            if normalized_start in haystack:
                return index

        logger.warning(
            "totem_debug_cycle.start_mode_not_found start_mode=%s fallback_index=%s",
            self.start_mode,
            self._active_mode_index(),
        )
        return self._active_mode_index()

    def _next_mode_index(self, mode_index: int) -> int:
        entry_count = len(self.game_modes.state.entries)
        if entry_count == 0:
            return 0
        return (mode_index + 1) % entry_count

    def _mode_name(self, mode_index: int) -> str:
        if not self.game_modes.state.entries:
            return "<empty>"
        entry = self.game_modes.state.entries[
            mode_index % len(self.game_modes.state.entries)
        ]
        label = self._mode_search_text(entry.title_renderer)
        return label or entry.title_renderer.name

    def _mode_search_text(self, renderer: StatefulBaseRenderer) -> str:
        chunks = [renderer.name]
        if isinstance(renderer, TitleScreen):
            chunks.append(renderer.title)
        if isinstance(renderer, TextRendering):
            provider = renderer._provider
            chunks.extend(getattr(provider, "_text", ()))
        if isinstance(renderer, ComposedRenderer):
            for child in renderer.renderers:
                chunks.append(self._mode_search_text(child))
        return " ".join(chunks)

    def _active_multi_scene(self) -> MultiScene | None:
        if not self.game_modes.state.entries:
            return None
        entry = self.game_modes.state.entries[self._active_mode_index()]
        return self._find_multi_scene(entry.renderer)

    def _reset_active_multi_scene(self) -> None:
        multi_scene = self._active_multi_scene()
        if multi_scene is not None and multi_scene.initialized:
            multi_scene.reset()

    def _find_multi_scene(
        self,
        renderer: StatefulBaseRenderer,
    ) -> MultiScene | None:
        if isinstance(renderer, MultiScene):
            return renderer
        if isinstance(renderer, ComposedRenderer):
            for child in renderer.renderers:
                multi_scene = self._find_multi_scene(child)
                if multi_scene is not None:
                    return multi_scene
        return None
