from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat

import numpy as np
import pygame
from manyfold import shutdown
from OpenGL.error import GLError
from OpenGL.GL import (GL_CLAMP_TO_EDGE, GL_COLOR_BUFFER_BIT,
                       GL_DEPTH_BUFFER_BIT, GL_MODELVIEW, GL_NEAREST,
                       GL_PROJECTION, GL_QUADS, GL_RGBA, GL_TEXTURE_2D,
                       GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
                       GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_UNSIGNED_BYTE,
                       glBegin, glBindTexture, glClear, glDeleteTextures,
                       glDisable, glEnable, glEnd, glGenTextures,
                       glLoadIdentity, glMatrixMode, glOrtho, glReadPixels,
                       glTexCoord2f, glTexImage2D, glTexParameteri,
                       glTexSubImage2D, glUseProgram, glVertex2f, glViewport)

from heart import DeviceDisplayMode
from heart.device import Cube, Orientation, Rectangle
from heart.device.local import LocalScreen
from heart.display.shaders.fullscreen import (FullscreenShaderRuntime,
                                              TextureUniform, UniformValue)
from heart.display.shaders.shader_templates.audio_storm import \
    __file__ as shader_template_location
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
DEFAULT_DEBUG_WIDTH = 2060
DEFAULT_DEBUG_HEIGHT = 1280
DEFAULT_DEBUG_FPS = 60
DEFAULT_DEBUG_LAYOUT = "rectangle"
AUDIO_TEXTURE_WIDTH = 256
AUDIO_TEXTURE_HEIGHT = 256
AUDIO_DECAY_PER_SECOND = 10.0
AUDIO_SCROLL_PIXELS_PER_SECOND = 0.5
ORBIT_ENABLED = True
ORBIT_INITIAL_PHASE = -0.4
ORBIT_RADIANS_PER_SECOND = 0.2
SYNTH_WRITE_X_CENTER = 0.055
SYNTH_WRITE_X_RANGE = 0.045
SYNTH_BAND_SHIFT_RANGE = 0.34
SYNTH_WRITE_GAIN_PER_SECOND = 16.0
TRIGGER_DEAD_ZONE = 0.05
GAMEPAD_DEAD_ZONE = 0.12
MIN_WIDTH_MULTIPLIER = 0.35
MAX_WIDTH_MULTIPLIER = 2.25
RIGHT_STICK_WIDTH_RANGE = 0.85
MIN_GAIN_MULTIPLIER = 2.25
MAX_GAIN_MULTIPLIER = 5.4
RIGHT_STICK_GAIN_RANGE = 1.0
ACCENT_GAIN_MULTIPLIER = 2.2
ACCENT_WIDTH_MULTIPLIER = 1.15


@dataclass(frozen=True, slots=True)
class FloatRange:
    low: float
    high: float

    def sample(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)


@dataclass(frozen=True, slots=True)
class SynthBand:
    center_y: float
    width_y: float
    gain: float
    noise: float = 0.0
    x_offset: float = 0.0
    width_x: float = 0.03


@dataclass(frozen=True, slots=True)
class SynthEnvelope:
    attack_s: float
    decay_s: float


@dataclass(frozen=True, slots=True)
class SynthVoice:
    name: str
    bands: tuple[SynthBand, ...]
    envelope: SynthEnvelope
    gain: float
    band_shift_multiplier: float = 1.0


@dataclass(frozen=True, slots=True)
class SynthPalette:
    kick: SynthVoice
    snare: SynthVoice
    closed_hat: SynthVoice
    open_hat: SynthVoice


@dataclass(frozen=True, slots=True)
class VoiceRandomizationBounds:
    band_count: tuple[int, int]
    center_y: FloatRange
    width_y: FloatRange
    band_gain: FloatRange
    noise: FloatRange
    x_offset: FloatRange
    width_x: FloatRange
    voice_gain: FloatRange
    band_shift_multiplier: FloatRange


KICK_VOICE = SynthVoice(
    name="kick",
    gain=1.25,
    envelope=SynthEnvelope(attack_s=0.0, decay_s=0.34),
    band_shift_multiplier=0.35,
    bands=(
        SynthBand(center_y=0.21, width_y=0.075, gain=0.25, width_x=0.034),
        # SynthBand(center_y=0.2, width_y=0.06, gain=0.42, width_x=0.03),
    ),
)
SNARE_VOICE = SynthVoice(
    name="snare",
    gain=0.95,
    envelope=SynthEnvelope(attack_s=0.0, decay_s=0.2),
    band_shift_multiplier=0.65,
    bands=(
        SynthBand(center_y=0.0, width_y=0.025, gain=0.15, width_x=0.014),
        # SynthBand(center_y=0.43, width_y=0.07, gain=0.8, width_x=0.028),
        # SynthBand(center_y=0.66, width_y=0.15, gain=0.36, noise=0.8, width_x=0.032),
    ),
)
CLOSED_HAT_VOICE = SynthVoice(
    name="closed_hat",
    gain=0.72,
    envelope=SynthEnvelope(attack_s=0.0, decay_s=0.09),
    band_shift_multiplier=0.28,
    bands=(
        SynthBand(center_y=0.42, width_y=0.035, gain=0.75, noise=0.65, width_x=0.018),
        SynthBand(center_y=0.55, width_y=0.024, gain=1.0, noise=0.9, width_x=0.014),
    ),
)
OPEN_HAT_VOICE = SynthVoice(
    name="open_hat",
    gain=0.68,
    envelope=SynthEnvelope(attack_s=0.0, decay_s=0.26),
    band_shift_multiplier=0.28,
    bands=(
        SynthBand(center_y=0.36, width_y=0.052, gain=0.62, noise=0.55, width_x=0.024),
        SynthBand(center_y=0.5, width_y=0.04, gain=1.0, noise=0.85, width_x=0.019),
        SynthBand(center_y=0.64, width_y=0.03, gain=0.42, noise=0.95, width_x=0.015),
    ),
)
DEFAULT_VOICE_PALETTE = SynthPalette(
    kick=KICK_VOICE,
    snare=SNARE_VOICE,
    closed_hat=CLOSED_HAT_VOICE,
    open_hat=OPEN_HAT_VOICE,
)
FREE_VOICE_RANDOMIZATION_BOUNDS = VoiceRandomizationBounds(
    band_count=(1, 4),
    center_y=FloatRange(0.0, 0.68),
    width_y=FloatRange(0.014, 0.11),
    band_gain=FloatRange(0.12, 0.9),
    noise=FloatRange(0.0, 0.85),
    x_offset=FloatRange(-0.02, 0.03),
    width_x=FloatRange(0.01, 0.05),
    voice_gain=FloatRange(0.5, 1.55),
    band_shift_multiplier=FloatRange(0.12, 0.8),
)


@dataclass
class AudioStormState:
    start_time: float
    peripheral_manager: PeripheralManager


class AudioStormScene(StatefulBaseRenderer[AudioStormState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self.shader_runtime = FullscreenShaderRuntime()
        self.window_size: tuple[int, int] | None = None
        self.render_size: tuple[int, int] | None = None
        self.tiled_mode = False
        self.display_texture: int | None = None
        self.audio_texture: int | None = None
        self.tile_pixels: np.ndarray | None = None
        self.audio_energy = np.zeros(
            (AUDIO_TEXTURE_HEIGHT, AUDIO_TEXTURE_WIDTH),
            dtype=np.float32,
        )
        self.audio_pixels = np.zeros(
            (AUDIO_TEXTURE_HEIGHT, AUDIO_TEXTURE_WIDTH, 4),
            dtype=np.uint8,
        )
        self._scroll_remainder = 0.0
        self._y_coordinates = np.linspace(
            0.0,
            1.0,
            AUDIO_TEXTURE_HEIGHT,
            dtype=np.float32,
        )
        self._x_coordinates = np.linspace(
            0.0,
            1.0,
            AUDIO_TEXTURE_WIDTH,
            dtype=np.float32,
        )
        noise_phase = (
            self._y_coordinates[:, None] * 311.7
            + self._x_coordinates[None, :] * 127.1
        )
        self._noise_texture = (
            0.5 + 0.5 * np.sin(noise_phase) * np.sin(noise_phase * 1.618)
        ).astype(np.float32)
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._gamepad_snapshots: tuple[GamepadSnapshotEvent, ...] = ()
        self._trigger_rest_values: dict[GamepadAxis, float] = {}
        self._voice_palette = DEFAULT_VOICE_PALETTE
        self._randomize_palette_was_held = False
        self._print_palette_was_held = False
        self._voice_rng = random.Random()

    def is_initialized(self) -> bool:
        return (
            super().is_initialized()
            and self.shader_runtime.is_initialized()
            and self.window_size is not None
            and self.render_size is not None
        )

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> AudioStormState:
        self.window_size = window.get_size()
        self.render_size = self._render_size(self.window_size, orientation)
        self.tiled_mode = self._should_tile(orientation)
        self._initialize_shader()
        return AudioStormState(
            start_time=time.monotonic(),
            peripheral_manager=peripheral_manager,
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        render_size = self._render_size(window.get_size(), orientation)
        if self.window_size != window.get_size() or self.render_size != render_size:
            self.window_size = window.get_size()
            self.render_size = render_size
            self.tiled_mode = self._should_tile(orientation)
            self._reset_tiled_resources()

        elapsed_s = self._elapsed_seconds(window.clock)
        self._refresh_keyboard_snapshot(self.state.peripheral_manager)
        self._refresh_gamepad_snapshot()
        self._process_palette_actions()
        self._update_audio_texture(elapsed_s)

        if self.tiled_mode:
            self._render_tiled(window)
            return

        self.shader_runtime.render(
            window,
            uniforms=self._shader_uniforms(),
            viewport_size=self.render_size,
        )

    def reset(self) -> None:
        self._reset_tiled_resources()
        self._reset_audio_resources()
        self.shader_runtime.reset()
        self.window_size = None
        self.render_size = None
        self.tiled_mode = False
        self.audio_energy.fill(0.0)
        self.audio_pixels.fill(0)
        self._scroll_remainder = 0.0
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._gamepad_snapshots = ()
        self._trigger_rest_values.clear()
        self._voice_palette = DEFAULT_VOICE_PALETTE
        self._randomize_palette_was_held = False
        self._print_palette_was_held = False
        self.initialized = False
        super().reset()

    def _refresh_keyboard_snapshot(
        self,
        peripheral_manager: PeripheralManager,
    ) -> None:
        input_io = getattr(peripheral_manager, "input_io", None)
        keyboard_controller = (
            input_io.keyboard
            if input_io is not None
            else getattr(peripheral_manager, "keyboard_controller", None)
        )
        if keyboard_controller is None:
            return
        try:
            self._keyboard_snapshot = keyboard_controller.sample()
        except (AttributeError, pygame.error):
            return

    def _initialize_shader(self) -> None:
        template_path = Path(shader_template_location).parent
        self.shader_runtime.initialize(fragment_path=template_path / "frag.glsl")

    def _shader_uniforms(self) -> dict[str, UniformValue]:
        assert self.render_size is not None
        assert self.audio_texture is not None
        return {
            "u_resolution": self.render_size,
            "u_time": time.monotonic() - self.state.start_time,
            "u_orbit_phase": self._orbit_phase(),
            "u_audio": TextureUniform(texture_id=self.audio_texture),
        }

    def _orbit_phase(self) -> float:
        if not ORBIT_ENABLED:
            return ORBIT_INITIAL_PHASE
        return float(
            ORBIT_INITIAL_PHASE
            + (time.monotonic() - self.state.start_time) * ORBIT_RADIANS_PER_SECOND
        )

    def _update_audio_texture(self, elapsed_s: float) -> None:
        self._ensure_audio_texture()
        self._decay_and_scroll_energy(elapsed_s)
        self._render_held_voices(elapsed_s)
        np.clip(self.audio_energy, 0.0, 1.0, out=self.audio_energy)
        self._write_audio_pixels()
        glBindTexture(GL_TEXTURE_2D, self.audio_texture)
        glTexSubImage2D(
            GL_TEXTURE_2D,
            0,
            0,
            0,
            AUDIO_TEXTURE_WIDTH,
            AUDIO_TEXTURE_HEIGHT,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.audio_pixels,
        )

    def _decay_and_scroll_energy(self, elapsed_s: float) -> None:
        if self._freeze_held():
            return
        self.audio_energy *= float(np.exp(-AUDIO_DECAY_PER_SECOND * elapsed_s))
        direction = -1.0 if self._reverse_scroll_held() else 1.0
        self._scroll_remainder += direction * AUDIO_SCROLL_PIXELS_PER_SECOND * elapsed_s
        scroll_pixels = int(abs(self._scroll_remainder))
        if scroll_pixels <= 0:
            return
        self._scroll_remainder -= direction * float(scroll_pixels)
        scroll_pixels = min(scroll_pixels, AUDIO_TEXTURE_WIDTH)
        if direction > 0.0:
            self.audio_energy[:] = np.roll(self.audio_energy, -scroll_pixels, axis=1)
            self.audio_energy[:, -scroll_pixels:] = 0.0
        else:
            self.audio_energy[:] = np.roll(self.audio_energy, scroll_pixels, axis=1)
            self.audio_energy[:, :scroll_pixels] = 0.0

    def _render_held_voices(self, elapsed_s: float) -> None:
        keys = self._keyboard_snapshot.pressed_keys
        write_x = self._write_x()
        band_shift = self._band_shift()
        width_multiplier = self._width_multiplier()
        gain_multiplier = self._gain_multiplier()
        if self._accent_held():
            width_multiplier *= ACCENT_WIDTH_MULTIPLIER
            gain_multiplier *= ACCENT_GAIN_MULTIPLIER
        left_held = pygame.K_q in keys or self._trigger_held(GamepadAxis.TRIGGER_LEFT)
        right_held = pygame.K_e in keys or self._trigger_held(GamepadAxis.TRIGGER_RIGHT)
        zl_held = pygame.K_z in keys or self._button_held(GamepadButton.ZL)
        zr_held = pygame.K_x in keys or self._button_held(GamepadButton.ZR)
        if left_held:
            self._render_voice(
                self._voice_palette.kick,
                write_x,
                band_shift,
                width_multiplier,
                gain_multiplier,
                elapsed_s,
            )
        if right_held:
            self._render_voice(
                self._voice_palette.snare,
                write_x,
                band_shift,
                width_multiplier,
                gain_multiplier,
                elapsed_s,
            )
        if zl_held:
            self._render_voice(
                self._voice_palette.closed_hat,
                write_x,
                band_shift,
                width_multiplier,
                gain_multiplier,
                elapsed_s,
            )
        if zr_held:
            self._render_voice(
                self._voice_palette.open_hat,
                write_x,
                band_shift,
                width_multiplier,
                gain_multiplier,
                elapsed_s,
            )

    def _render_voice(
        self,
        voice: SynthVoice,
        write_x: float,
        band_shift: float,
        width_multiplier: float,
        gain_multiplier: float,
        elapsed_s: float,
    ) -> None:
        for band in voice.bands:
            center_y = self._clamp(
                band.center_y
                + band_shift * voice.band_shift_multiplier,
                0.0,
                1.0,
            )
            x_width = max(band.width_x * width_multiplier, 0.001)
            y_width = max(band.width_y * width_multiplier, 0.001)
            x_profile = np.exp(
                -0.5
                * ((self._x_coordinates - write_x - band.x_offset) / x_width)
                ** 2
            )
            y_profile = np.exp(-0.5 * ((self._y_coordinates - center_y) / y_width) ** 2)
            band_profile = y_profile[:, None] * x_profile[None, :]
            if band.noise > 0.0:
                band_profile *= 1.0 + band.noise * self._noise_texture
            self.audio_energy += (
                band_profile
                * voice.gain
                * band.gain
                * gain_multiplier
                * elapsed_s
                * SYNTH_WRITE_GAIN_PER_SECOND
            ).astype(np.float32)

    def _write_x(self) -> float:
        stick_x = self._axis_value(
            GamepadAxis.LEFT_X,
            dead_zone=GAMEPAD_DEAD_ZONE,
        )
        keyboard_x = float(pygame.K_RIGHT in self._keyboard_snapshot.pressed_keys) - float(
            pygame.K_LEFT in self._keyboard_snapshot.pressed_keys
        )
        return self._clamp(
            SYNTH_WRITE_X_CENTER + (stick_x + keyboard_x) * SYNTH_WRITE_X_RANGE,
            0.0,
            1.0,
        )

    def _band_shift(self) -> float:
        stick_y = -self._axis_value(
            GamepadAxis.LEFT_Y,
            dead_zone=GAMEPAD_DEAD_ZONE,
        )
        keyboard_y = float(pygame.K_UP in self._keyboard_snapshot.pressed_keys) - float(
            pygame.K_DOWN in self._keyboard_snapshot.pressed_keys
        )
        return (stick_y + keyboard_y) * SYNTH_BAND_SHIFT_RANGE

    def _width_multiplier(self) -> float:
        stick_x = self._axis_value(
            GamepadAxis.RIGHT_X,
            dead_zone=GAMEPAD_DEAD_ZONE,
        )
        return self._clamp(
            1.0 + stick_x * RIGHT_STICK_WIDTH_RANGE,
            MIN_WIDTH_MULTIPLIER,
            MAX_WIDTH_MULTIPLIER,
        )

    def _gain_multiplier(self) -> float:
        stick_y = -self._axis_value(
            GamepadAxis.RIGHT_Y,
            dead_zone=GAMEPAD_DEAD_ZONE,
        )
        return self._clamp(
            1.0 + stick_y * RIGHT_STICK_GAIN_RANGE,
            MIN_GAIN_MULTIPLIER,
            MAX_GAIN_MULTIPLIER,
        )

    def _accent_held(self) -> bool:
        return pygame.K_SPACE in self._keyboard_snapshot.pressed_keys or (
            self._button_held(GamepadButton.SOUTH)
        )

    def _reverse_scroll_held(self) -> bool:
        return pygame.K_d in self._keyboard_snapshot.pressed_keys

    def _process_palette_actions(self) -> None:
        randomize_held = self._randomize_palette_held()
        if randomize_held and not self._randomize_palette_was_held:
            self._voice_palette = self._randomized_voice_palette()
        self._randomize_palette_was_held = randomize_held

        print_held = self._print_palette_held()
        if print_held and not self._print_palette_was_held:
            logger.info(
                "Current Audio Storm SynthPalette:\n%s",
                pformat(self._voice_palette, width=88, sort_dicts=False),
            )
        self._print_palette_was_held = print_held

    def _randomize_palette_held(self) -> bool:
        return pygame.K_c in self._keyboard_snapshot.pressed_keys or (
            self._button_held(GamepadButton.EAST)
        )

    def _print_palette_held(self) -> bool:
        return pygame.K_PERIOD in self._keyboard_snapshot.pressed_keys

    def _randomized_voice_palette(self) -> SynthPalette:
        return SynthPalette(
            kick=self._randomized_voice(KICK_VOICE, FREE_VOICE_RANDOMIZATION_BOUNDS),
            snare=self._randomized_voice(SNARE_VOICE, FREE_VOICE_RANDOMIZATION_BOUNDS),
            closed_hat=self._randomized_voice(
                CLOSED_HAT_VOICE,
                FREE_VOICE_RANDOMIZATION_BOUNDS,
            ),
            open_hat=self._randomized_voice(
                OPEN_HAT_VOICE,
                FREE_VOICE_RANDOMIZATION_BOUNDS,
            ),
        )

    def _randomized_voice(
        self,
        default_voice: SynthVoice,
        bounds: VoiceRandomizationBounds,
    ) -> SynthVoice:
        band_count = self._voice_rng.randint(*bounds.band_count)
        bands = tuple(
            SynthBand(
                center_y=bounds.center_y.sample(self._voice_rng),
                width_y=bounds.width_y.sample(self._voice_rng),
                gain=bounds.band_gain.sample(self._voice_rng),
                noise=bounds.noise.sample(self._voice_rng),
                x_offset=bounds.x_offset.sample(self._voice_rng),
                width_x=bounds.width_x.sample(self._voice_rng),
            )
            for _ in range(band_count)
        )
        return SynthVoice(
            name=default_voice.name,
            bands=bands,
            envelope=default_voice.envelope,
            gain=bounds.voice_gain.sample(self._voice_rng),
            band_shift_multiplier=bounds.band_shift_multiplier.sample(self._voice_rng),
        )

    def _freeze_held(self) -> bool:
        return pygame.K_a in self._keyboard_snapshot.pressed_keys or (
            self._button_held(GamepadButton.WEST)
        )

    def _write_audio_pixels(self) -> None:
        blue = np.asarray(self.audio_energy * 255.0, dtype=np.uint8)
        weighted = np.asarray(
            self.audio_energy * self._y_coordinates[:, None] * 255.0,
            dtype=np.uint8,
        )
        waveform = np.asarray(
            np.sqrt(np.clip(self.audio_energy, 0.0, 1.0)) * 180.0,
            dtype=np.uint8,
        )
        self.audio_pixels[:, :, 0] = weighted
        self.audio_pixels[:, :, 1] = waveform
        self.audio_pixels[:, :, 2] = blue
        self.audio_pixels[:, :, 3] = 255

    def _render_tiled(self, window: DisplayContext) -> None:
        assert self.render_size is not None
        assert self.window_size is not None
        self._ensure_tiled_resources()
        assert self.tile_pixels is not None
        assert self.display_texture is not None

        tile_width, tile_height = self.render_size
        self.shader_runtime.draw(
            uniforms=self._shader_uniforms(),
            viewport_size=self.render_size,
        )
        glReadPixels(
            0,
            0,
            tile_width,
            tile_height,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.tile_pixels,
        )
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glTexSubImage2D(
            GL_TEXTURE_2D,
            0,
            0,
            0,
            tile_width,
            tile_height,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.tile_pixels,
        )
        self._render_tiled_texture()
        self.shader_runtime.read_to_surface(window, size=self.window_size)

    def _ensure_audio_texture(self) -> None:
        if self.audio_texture is not None:
            return
        self.audio_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.audio_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            AUDIO_TEXTURE_WIDTH,
            AUDIO_TEXTURE_HEIGHT,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.audio_pixels,
        )

    def _ensure_tiled_resources(self) -> None:
        assert self.render_size is not None
        width, height = self.render_size
        if (
            self.tile_pixels is None
            or self.tile_pixels.shape[0] != height
            or self.tile_pixels.shape[1] != width
        ):
            self.tile_pixels = np.zeros((height, width, 4), dtype=np.uint8)
        if self.display_texture is not None:
            return
        self.display_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )

    def _render_tiled_texture(self) -> None:
        assert self.display_texture is not None
        assert self.render_size is not None
        assert self.window_size is not None
        tile_width, tile_height = self.render_size
        glViewport(0, 0, self.window_size[0], self.window_size[1])
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.window_size[0], 0, self.window_size[1], -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glUseProgram(0)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        for x in range(0, self.window_size[0], tile_width):
            for y in range(0, self.window_size[1], tile_height):
                glBegin(GL_QUADS)
                glTexCoord2f(0, 0)
                glVertex2f(x, y)
                glTexCoord2f(1, 0)
                glVertex2f(x + tile_width, y)
                glTexCoord2f(1, 1)
                glVertex2f(x + tile_width, y + tile_height)
                glTexCoord2f(0, 1)
                glVertex2f(x, y + tile_height)
                glEnd()
        glDisable(GL_TEXTURE_2D)

    def _reset_tiled_resources(self) -> None:
        if self.display_texture is not None:
            try:
                glDeleteTextures([self.display_texture])
            except GLError:
                pass
        self.display_texture = None
        self.tile_pixels = None

    def _reset_audio_resources(self) -> None:
        if self.audio_texture is not None:
            try:
                glDeleteTextures([self.audio_texture])
            except GLError:
                pass
        self.audio_texture = None

    def _trigger_held(self, axis: GamepadAxis) -> bool:
        return any(
            self._trigger_pressure(
                axis,
                event.snapshot.axis_value(axis, dead_zone=0.0),
            )
            >= TRIGGER_DEAD_ZONE
            for event in self._gamepad_snapshots
        )

    def _set_keyboard_snapshot(self, snapshot: KeyboardSnapshot) -> None:
        self._keyboard_snapshot = snapshot

    def _refresh_gamepad_snapshot(self) -> None:
        self._gamepad_snapshots = self.state.peripheral_manager.input_io.gamepad.sample()
        if not self._gamepad_snapshots:
            self._trigger_rest_values.clear()
            return
        for axis in (GamepadAxis.TRIGGER_LEFT, GamepadAxis.TRIGGER_RIGHT):
            for event in self._gamepad_snapshots:
                self._trigger_rest_values.setdefault(
                    axis,
                    event.snapshot.axis_value(axis, dead_zone=0.0),
                )

    def _trigger_pressure(self, axis: GamepadAxis, raw_value: float) -> float:
        rest_value = self._trigger_rest_values.get(axis)
        if rest_value is not None:
            if rest_value <= -0.5:
                return self._clamp(
                    (raw_value - rest_value) / (1.0 - rest_value),
                    0.0,
                    1.0,
                )
            if rest_value >= 0.5:
                return self._clamp(
                    (rest_value - raw_value) / (rest_value + 1.0),
                    0.0,
                    1.0,
                )
            return self._clamp(abs(raw_value - rest_value), 0.0, 1.0)
        if raw_value < 0.0:
            return self._clamp((raw_value + 1.0) * 0.5, 0.0, 1.0)
        return self._clamp(raw_value, 0.0, 1.0)

    def _button_held(self, button: GamepadButton) -> bool:
        return any(
            event.snapshot.button_held(button)
            for event in self._gamepad_snapshots
        )

    def _axis_value(self, axis: GamepadAxis, *, dead_zone: float) -> float:
        values = [
            event.snapshot.axis_value(axis, dead_zone=dead_zone)
            for event in self._gamepad_snapshots
        ]
        if not values:
            return 0.0
        return max(values, key=abs)

    @staticmethod
    def _elapsed_seconds(clock: pygame.time.Clock | None) -> float:
        if clock is None:
            return 1.0 / 60.0
        elapsed_s = clock.get_time() / 1000.0
        if elapsed_s <= 0.0:
            return 1.0 / 60.0
        return min(elapsed_s, 0.1)

    @staticmethod
    def _render_size(
        window_size: tuple[int, int],
        orientation: Orientation,
    ) -> tuple[int, int]:
        if AudioStormScene._should_tile(orientation):
            layout = orientation.layout
            return (
                max(1, window_size[0] // layout.columns),
                max(1, window_size[1] // layout.rows),
            )
        return window_size

    @staticmethod
    def _should_tile(orientation: Orientation) -> bool:
        layout = orientation.layout
        return layout.columns > 1 or layout.rows > 1

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return min(max(value, low), high)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Audio Storm renderer directly in a local debug window.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_DEBUG_WIDTH,
        help="Window width in pixels.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_DEBUG_HEIGHT,
        help="Window height in pixels.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_DEBUG_FPS,
        help="Frame cap for the debug loop.",
    )
    parser.add_argument(
        "--layout",
        choices=(DEFAULT_DEBUG_LAYOUT, "cube"),
        default=DEFAULT_DEBUG_LAYOUT,
        help="Render as a single rectangle or use the cube tiling path.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    orientation = (
        Cube.sides()
        if args.layout == "cube"
        else Rectangle.with_layout(columns=1, rows=1)
    )

    device = LocalScreen(width=args.width, height=args.height, orientation=orientation)
    container = build_runtime_container(device=device)
    peripheral_manager = container.resolve(PeripheralManager)
    peripheral_runtime = container.resolve(PeripheralRuntime)
    display = container.resolve(DisplayContext)
    scene = AudioStormScene()

    logger.info(
        "Starting standalone Audio Storm debug window width=%s height=%s layout=%s fps=%s",
        args.width,
        args.height,
        args.layout,
        args.fps,
    )

    display.initialize()
    display.configure_window(DeviceDisplayMode.OPENGL)
    peripheral_manager.detect()
    peripheral_manager.start()

    running = True
    try:
        scene.initialize(
            window=display,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            peripheral_runtime.tick()
            scene.real_process(window=display, orientation=orientation)
            pygame.display.flip()
            if display.clock is None:
                raise RuntimeError(
                    "Standalone Audio Storm debug loop did not initialize a clock"
                )
            display.clock.tick(args.fps)
            peripheral_runtime.tick()
        scene.reset()
    finally:
        shutdown.on_next(True)
        shutdown.on_completed()
        shutdown.dispose()
        pygame.quit()


if __name__ == "__main__":
    main()
