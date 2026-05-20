from __future__ import annotations

import random
import time
from dataclasses import replace

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.input import GamepadButton
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers import StatefulBaseRenderer
from heart.renderers.reaction_time.state import (ReactionPhase,
                                                 ReactionPlayerState,
                                                 ReactionTimeState,
                                                 new_reaction_round,
                                                 reaction_winner)
from heart.renderers.tetris.direct_gamepad import (DirectGamepadSnapshot,
                                                   DirectTetrisGamepads)
from heart.runtime.display_context import DisplayContext

RNG_NAMESPACE = "reaction-time"
PLAYER_COUNT = 4
IDENTIFY_DURATION_S = 2.0
COUNTDOWN_DURATION_S = 3.0
MIN_GO_DELAY_S = 0.5
MAX_GO_DELAY_S = 5.0
MAX_REACTION_WINDOW_S = 3.0
RESULTS_DURATION_S = 4.0
PIXEL_FONT_PATH = "Grand9K Pixel.ttf"
BACKGROUND_COLOR = pygame.Color(3, 5, 10)
PANEL_COLORS = (
    pygame.Color(10, 22, 34),
    pygame.Color(28, 20, 6),
    pygame.Color(22, 12, 32),
    pygame.Color(7, 25, 15),
)
PLAYER_ACCENTS = (
    pygame.Color(0, 220, 255),
    pygame.Color(255, 211, 64),
    pygame.Color(185, 112, 255),
    pygame.Color(74, 222, 128),
)
TEXT_COLOR = pygame.Color(245, 250, 255)
DIM_TEXT_COLOR = pygame.Color(104, 119, 138)
FALSE_START_COLOR = pygame.Color(255, 55, 76)
GO_COLOR = pygame.Color(80, 255, 138)
REACTION_BUTTONS = (
    GamepadButton.SOUTH,
    GamepadButton.EAST,
    GamepadButton.WEST,
    GamepadButton.ZL,
    GamepadButton.ZR,
    GamepadButton.L3,
    GamepadButton.R3,
)
KEYBOARD_KEYS_BY_PLAYER = (
    (pygame.K_1, pygame.K_q, pygame.K_a),
    (pygame.K_2, pygame.K_w, pygame.K_s),
    (pygame.K_3, pygame.K_e, pygame.K_d),
    (pygame.K_4, pygame.K_r, pygame.K_f),
)


class ReactionTimeRenderer(StatefulBaseRenderer[ReactionTimeState]):
    def __init__(
        self,
        *,
        randomness: RandomnessProvider | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._rng = rng or (randomness or RandomnessProvider()).rng(RNG_NAMESPACE)
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self._gamepads = DirectTetrisGamepads()
        self._fonts: dict[int, pygame.font.Font] = {}
        self._native_surface: pygame.Surface | None = None

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ReactionTimeState:
        del window, peripheral_manager, orientation
        return new_reaction_round(
            now=time.monotonic(),
            player_count=PLAYER_COUNT,
            round_number=1,
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if window.screen is None:
            raise RuntimeError("ReactionTimeRenderer requires an initialized display")

        now = time.monotonic()
        self._gamepads.refresh(player_count=PLAYER_COUNT)
        snapshots = tuple(
            self._gamepads.snapshot_for_slot(player_index)
            for player_index in range(PLAYER_COUNT)
        )
        keyboard_pressed = self._keyboard_pressed()
        state = self._advance_phase_before_inputs(now)
        state = self._apply_inputs(state, now, snapshots, keyboard_pressed)
        state = self._advance_phase_after_inputs(state, now)
        self.set_state(state)

        render_target = self._native_render_target(window)
        self._draw(
            render_target,
            window.device.individual_display_size(),
            orientation.layout.columns,
            snapshots,
            keyboard_pressed,
            now,
        )
        if render_target is not window.screen:
            pygame.transform.scale(render_target, window.screen.get_size(), window.screen)

    def reset(self) -> None:
        self.set_state(
            new_reaction_round(
                now=time.monotonic(),
                player_count=PLAYER_COUNT,
                round_number=self.state.round_number + 1 if self._state else 1,
            )
        )

    def _advance_phase_before_inputs(self, now: float) -> ReactionTimeState:
        state = self.state
        elapsed = now - state.phase_started_at
        if state.phase is ReactionPhase.IDENTIFY and elapsed >= IDENTIFY_DURATION_S:
            return replace(
                state,
                phase=ReactionPhase.COUNTDOWN,
                phase_started_at=now,
            )
        if state.phase is ReactionPhase.COUNTDOWN and elapsed >= COUNTDOWN_DURATION_S:
            return replace(
                state,
                phase=ReactionPhase.WAIT,
                phase_started_at=now,
                go_at=now + self._rng.uniform(MIN_GO_DELAY_S, MAX_GO_DELAY_S),
            )
        if state.phase is ReactionPhase.WAIT and now >= state.go_at:
            return replace(
                state,
                phase=ReactionPhase.GO,
                phase_started_at=state.go_at,
            )
        if state.phase is ReactionPhase.RESULTS and elapsed >= RESULTS_DURATION_S:
            return new_reaction_round(
                now=now,
                player_count=PLAYER_COUNT,
                round_number=state.round_number + 1,
            )
        return state

    def _apply_inputs(
        self,
        state: ReactionTimeState,
        now: float,
        snapshots: tuple[DirectGamepadSnapshot, ...],
        keyboard_pressed: tuple[bool, ...],
    ) -> ReactionTimeState:
        if state.phase is ReactionPhase.IDENTIFY:
            return state
        players = list(state.players)
        for player_index, player in enumerate(players):
            if player.false_start or player.reaction_time_s is not None:
                continue
            pressed = self._reaction_pressed(snapshots[player_index]) or keyboard_pressed[
                player_index
            ]
            if not pressed:
                continue
            if state.phase in (ReactionPhase.COUNTDOWN, ReactionPhase.WAIT):
                players[player_index] = replace(player, false_start=True)
            elif state.phase is ReactionPhase.GO:
                players[player_index] = replace(
                    player,
                    reaction_time_s=max(0.0, now - state.go_at),
                )
        return replace(state, players=tuple(players))

    def _advance_phase_after_inputs(
        self,
        state: ReactionTimeState,
        now: float,
    ) -> ReactionTimeState:
        if state.phase is not ReactionPhase.GO:
            return state
        elapsed = now - state.go_at
        active_players = [
            player for player in state.players if not player.false_start
        ]
        all_active_players_answered = active_players and all(
            player.reaction_time_s is not None for player in active_players
        )
        if elapsed >= MAX_REACTION_WINDOW_S or all_active_players_answered:
            return replace(
                state,
                phase=ReactionPhase.RESULTS,
                phase_started_at=now,
            )
        return state

    def _native_render_target(self, window: DisplayContext) -> pygame.Surface:
        if window.screen is None:
            raise RuntimeError("ReactionTimeRenderer requires an initialized display")
        native_size = window.device.full_display_size()
        if window.screen.get_size() == native_size:
            return window.screen
        if self._native_surface is None or self._native_surface.get_size() != native_size:
            self._native_surface = pygame.Surface(native_size, pygame.SRCALPHA)
        return self._native_surface

    def _draw(
        self,
        screen: pygame.Surface,
        panel_size: tuple[int, int],
        panel_columns: int,
        snapshots: tuple[DirectGamepadSnapshot, ...],
        keyboard_pressed: tuple[bool, ...],
        now: float,
    ) -> None:
        screen.fill(BACKGROUND_COLOR)
        panel_width, panel_height = panel_size
        columns = max(1, panel_columns)
        winner = reaction_winner(self.state.players)
        for player_index, player in enumerate(self.state.players):
            col = player_index % columns
            row = player_index // columns
            panel = pygame.Rect(
                col * panel_width,
                row * panel_height,
                panel_width,
                panel_height,
            )
            active_input = self._reaction_pressed(
                snapshots[player_index]
            ) or keyboard_pressed[player_index]
            self._draw_panel(
                screen,
                panel,
                player_index,
                player,
                active_input,
                winner,
                now,
            )

    def _draw_panel(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player_index: int,
        player: ReactionPlayerState,
        active_input: bool,
        winner: int | None,
        now: float,
    ) -> None:
        accent = PLAYER_ACCENTS[player_index % len(PLAYER_ACCENTS)]
        panel_color = PANEL_COLORS[player_index % len(PANEL_COLORS)]
        pygame.draw.rect(screen, panel_color, panel)
        pygame.draw.rect(screen, accent, panel, width=1)
        self._draw_player_label(screen, panel, player_index, accent)
        self._draw_input_dot(screen, panel, active_input, accent)

        if player.false_start:
            self._draw_center_text(screen, panel, "Chill", FALSE_START_COLOR, 17)
            self._draw_bottom_text(screen, panel, "bro", FALSE_START_COLOR, 12)
            return

        match self.state.phase:
            case ReactionPhase.IDENTIFY:
                self._draw_center_text(screen, panel, "press", TEXT_COLOR, 13)
                self._draw_bottom_text(screen, panel, "match", DIM_TEXT_COLOR, 9)
            case ReactionPhase.COUNTDOWN:
                self._draw_center_text(
                    screen,
                    panel,
                    self._countdown_label(now),
                    TEXT_COLOR,
                    28,
                )
                self._draw_bottom_text(screen, panel, "wait", DIM_TEXT_COLOR, 9)
            case ReactionPhase.WAIT:
                self._draw_center_text(screen, panel, "...", DIM_TEXT_COLOR, 24)
                self._draw_bottom_text(screen, panel, "wait", DIM_TEXT_COLOR, 9)
            case ReactionPhase.GO:
                if player.reaction_time_s is None:
                    self._draw_center_text(screen, panel, "GO!", GO_COLOR, 23)
                else:
                    self._draw_reaction_time(screen, panel, player.reaction_time_s)
            case ReactionPhase.RESULTS:
                if player.reaction_time_s is None:
                    self._draw_center_text(screen, panel, "MISS", DIM_TEXT_COLOR, 17)
                else:
                    self._draw_reaction_time(screen, panel, player.reaction_time_s)
                if winner == player_index:
                    self._draw_bottom_text(screen, panel, "WIN", GO_COLOR, 12)

    def _draw_player_label(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player_index: int,
        color: pygame.Color,
    ) -> None:
        surface = self._font(10).render(f"P{player_index + 1}", False, color)
        screen.blit(surface, (panel.left + 3, panel.top + 3))

    def _draw_input_dot(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        active_input: bool,
        color: pygame.Color,
    ) -> None:
        dot_color = color if active_input else pygame.Color(35, 45, 56)
        radius = 4 if active_input else 2
        pygame.draw.circle(screen, dot_color, (panel.right - 8, panel.top + 8), radius)

    def _draw_reaction_time(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        reaction_time_s: float,
    ) -> None:
        text = f"{reaction_time_s * 1000:.0f}"
        self._draw_center_text(screen, panel, text, TEXT_COLOR, 20)
        self._draw_bottom_text(screen, panel, "ms", DIM_TEXT_COLOR, 9)

    def _draw_center_text(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        text: str,
        color: pygame.Color,
        font_size: int,
    ) -> None:
        surface = self._fit_text(text, color, font_size, max_width=panel.width - 4)
        rect = surface.get_rect(center=panel.center)
        screen.blit(surface, rect)

    def _draw_bottom_text(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        text: str,
        color: pygame.Color,
        font_size: int,
    ) -> None:
        surface = self._fit_text(text, color, font_size, max_width=panel.width - 4)
        rect = surface.get_rect(midbottom=(panel.centerx, panel.bottom - 4))
        screen.blit(surface, rect)

    def _fit_text(
        self,
        text: str,
        color: pygame.Color,
        font_size: int,
        *,
        max_width: int,
    ) -> pygame.Surface:
        size = font_size
        while size > 6:
            surface = self._font(size).render(text, False, color)
            if surface.get_width() <= max_width:
                return surface
            size -= 1
        return self._font(6).render(text, False, color)

    def _countdown_label(self, now: float) -> str:
        elapsed = max(0.0, now - self.state.phase_started_at)
        return str(max(1, 3 - int(elapsed)))

    def _reaction_pressed(self, snapshot: DirectGamepadSnapshot) -> bool:
        if any(snapshot.button_held(button) for button in REACTION_BUTTONS):
            return True
        return snapshot.dpad.x != 0 or snapshot.dpad.y != 0

    def _keyboard_pressed(self) -> tuple[bool, ...]:
        try:
            pygame.event.pump()
            keys = pygame.key.get_pressed()
        except pygame.error:
            return tuple(False for _ in range(PLAYER_COUNT))
        return tuple(
            any(keys[key] for key in player_keys)
            for player_keys in KEYBOARD_KEYS_BY_PLAYER
        )

    def _font(self, size: int) -> pygame.font.Font:
        if not pygame.font.get_init():
            pygame.font.init()
        font = self._fonts.get(size)
        if font is None:
            try:
                font = pygame.font.Font(Loader.resolve_path(PIXEL_FONT_PATH), size)
            except (FileNotFoundError, pygame.error):
                font = pygame.font.Font(None, size)
            self._fonts[size] = font
        return font
