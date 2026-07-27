from __future__ import annotations

import gc
import os
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypeVar

import numpy as np
import pygame
from heart_device_manager.environment import is_pi

from heart import DeviceDisplayMode
from heart.device import Device
from heart.navigation import ComposedRenderer, MultiScene
from heart.renderers.emoji_overlay import FloatingEmojiOverlayRenderer
from heart.runtime.active_game_loop import set_active_game_loop
from heart.runtime.container import (build_runtime_container,
                                     configure_runtime_container)
from heart.runtime.display_context import DisplayContext
from heart.runtime.domain_lifecycle import (HeartLifecycleEmitter,
                                            HeartLifecycleKind,
                                            HeartLifecycleReason,
                                            pipeline_lifecycle_topic)
from heart.runtime.game_loop.components import GameLoopComponents
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

try:
    import resource
except ImportError:  # pragma: no cover - resource is available on supported targets.
    resource = None

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer
    from heart.runtime.container import RuntimeContainer

logger = get_logger(__name__)

ACTIVE_GAME_LOOP: "GameLoop" | None = None
DependencyT = TypeVar("DependencyT")
DEFAULT_MAX_FPS = 500
EDGE_THRESHOLD = 1
MAX_FPS_ENV_VAR = "HEART_MAX_FPS"
PERF_LOG_ENABLED_ENV_VAR = "HEART_RENDER_PERF_LOG"
PERF_LOG_INTERVAL_ENV_VAR = "HEART_RENDER_PERF_LOG_INTERVAL"
DEFAULT_PERF_LOG_INTERVAL_SECONDS = 2.0
ENV_TRUE_VALUES = {"1", "true", "yes", "on"}


def _elapsed_ms_since(start_seconds: float) -> float:
    return (time.perf_counter() - start_seconds) * 1000.0


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ENV_TRUE_VALUES


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        logger.warning(
            "Invalid %s=%r; using %.2f",
            name,
            raw_value,
            default,
        )
        return default


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid %s=%r; using %s",
            name,
            raw_value,
            default,
        )
        return default
    if parsed < minimum:
        logger.warning(
            "Invalid %s=%r; using %s",
            name,
            raw_value,
            default,
        )
        return default
    return parsed


class GameLoop:
    def __init__(
        self,
        device: Device,
        resolver: RuntimeContainer | None = None,
        max_fps: int = DEFAULT_MAX_FPS,
    ) -> None:
        self.context_container = self._prepare_container(
            device=device,
            resolver=resolver,
        )
        self.initialized = False
        self.device = self.context_container.resolve(Device)

        self.max_fps = min(
            _env_int(MAX_FPS_ENV_VAR, max_fps, minimum=1),
            Configuration.runtime_max_fps(),
        )
        self.components = self._load_components()

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.edge_thresh = EDGE_THRESHOLD
        self._temporary_renderer: "StatefulBaseRenderer[Any]" | None = None
        self._temporary_renderer_deadline_monotonic: float | None = None
        self._emoji_overlay_renderer: FloatingEmojiOverlayRenderer | None = None
        self._frame_index = 0
        self._last_perf_log_monotonic = 0.0
        self._frame_pipeline_under_pressure = False
        self._pipeline_lifecycle = HeartLifecycleEmitter(
            pipeline_lifecycle_topic()
        )

    def _one_loop(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> dict[str, float]:
        if self.components.display.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        if self.components.display.clock is None:
            raise RuntimeError("GameLoop clock is not initialized")

        timings: dict[str, float] = {}

        started_at = time.perf_counter()
        render_surface = self.render_frame(renderers)
        timings["render_ms"] = _elapsed_ms_since(started_at)

        if render_surface is not None:
            started_at = time.perf_counter()
            self._apply_post_processors(render_surface)
            timings["post_ms"] = _elapsed_ms_since(started_at)

            started_at = time.perf_counter()
            self.components.display.screen.fill("black")
            timings["clear_ms"] = _elapsed_ms_since(started_at)

            started_at = time.perf_counter()
            self.components.display.blit(render_surface, (0, 0))
            timings["blit_ms"] = _elapsed_ms_since(started_at)

            started_at = time.perf_counter()
            pygame.display.flip()
            timings["flip_ms"] = _elapsed_ms_since(started_at)

            started_at = time.perf_counter()
            self.device.set_screen(self.components.display.screen)
            timings["device_ms"] = _elapsed_ms_since(started_at)

        return timings

    def _apply_post_processors(self, surface: pygame.Surface) -> None:
        post_processors = self.components.game_modes.get_post_processors()
        if not post_processors:
            return
        post_context = DisplayContext(
            device=self.device,
            screen=surface,
            clock=self.components.display.clock,
            last_render_mode=self.components.display.last_render_mode,
            can_configure_display=False,
        )
        for renderer in post_processors:
            if not renderer.initialized:
                renderer.initialize(
                    window=post_context,
                    peripheral_manager=self.components.peripheral_manager,
                    orientation=self.device.orientation,
                )
            renderer._internal_process(
                window=post_context,
                peripheral_manager=self.components.peripheral_manager,
                orientation=self.device.orientation,
            )

    def resolve(self, dependency: type[DependencyT]) -> DependencyT:
        return self.context_container.resolve(dependency)

    def compose(
        self,
        renderers: list[
            "StatefulBaseRenderer[Any]" | type["StatefulBaseRenderer[Any]"]
        ],
    ) -> ComposedRenderer:
        result = self.context_container.resolve(ComposedRenderer)
        result.add_renderer(*renderers)
        return result

    def add_mode(
        self,
        title: str
        | list["StatefulBaseRenderer[Any]" | type["StatefulBaseRenderer[Any]"]]
        | type["StatefulBaseRenderer[Any]"]
        | "StatefulBaseRenderer[Any]"
        | None = None,
    ) -> ComposedRenderer:
        return self.components.game_modes.add_mode(title=title)

    def add_scene(self) -> MultiScene:
        return self.components.game_modes.add_scene()

    def add_sleep_mode(self) -> None:
        self.components.game_modes.add_sleep_mode()

    @classmethod
    def get_game_loop(cls) -> "GameLoop" | None:
        return ACTIVE_GAME_LOOP

    @classmethod
    def set_game_loop(cls, loop: "GameLoop") -> None:
        global ACTIVE_GAME_LOOP
        ACTIVE_GAME_LOOP = loop
        set_active_game_loop(loop)

    def start(self) -> None:
        logger.info("Starting GameLoop")
        if not self.initialized:
            logger.info("GameLoop not yet initialized, initializing...")
            self._ensure_initialized()
            logger.info("Finished initializing GameLoop.")

        if self.components.game_modes.is_empty():
            raise RuntimeError("Unable to start as no GameModes were added.")

        # Initialize all renderers

        self.running = True
        logger.info("Entering main loop.")

        logger.info("Initializing game modes.")
        self._initialize_game_modes()
        logger.info("Ensuring display is initialized.")
        self._ensure_display_initialized()
        logger.info("Configuring streaming.")
        self.components.peripheral_runtime.configure_streaming()

        try:
            self._run_main_loop()
        finally:
            logger.info("Shutting down GameLoop.")

            self.components.peripheral_runtime.close()
            self.components.peripheral_manager.stop()
            pygame.quit()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.components.display.set_screen(screen)
        pygame.display.flip()
        self.components.peripheral_manager.window.on_next(
            self.components.display.screen
        )

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.components.display.set_clock(clock)
        self.components.peripheral_runtime.set_clock(self.components.display.clock)

    @property
    def screen(self) -> pygame.Surface | None:
        return self.components.display.screen

    @property
    def clock(self) -> pygame.time.Clock | None:
        return self.components.display.clock

    def _select_renderers(self) -> list["StatefulBaseRenderer[Any]"]:
        temporary_renderer = self._active_temporary_renderer()
        if temporary_renderer is not None:
            renderers = [temporary_renderer]
        else:
            base_renderers = self.components.game_modes.get_renderers()
            renderers = list(base_renderers) if base_renderers else []
        emoji_overlay = self._active_emoji_overlay_renderer()
        if emoji_overlay is not None:
            renderers.append(emoji_overlay)
        return renderers

    def present_temporary_renderer(
        self,
        renderer: "StatefulBaseRenderer[Any]",
        *,
        duration_seconds: float,
    ) -> None:
        self._clear_temporary_renderer()
        self._temporary_renderer = renderer
        self._temporary_renderer_deadline_monotonic = time.monotonic() + max(
            0.0, duration_seconds
        )

    def clear_temporary_renderer(self) -> None:
        self._clear_temporary_renderer()

    def present_floating_emoji(self, emoji: str) -> None:
        if self._emoji_overlay_renderer is None:
            self._emoji_overlay_renderer = FloatingEmojiOverlayRenderer()
        if not self._emoji_overlay_renderer.initialized:
            self._ensure_display_initialized()
            self._emoji_overlay_renderer.initialize(
                window=self.components.display,
                peripheral_manager=self.components.peripheral_manager,
                orientation=self.device.orientation,
            )
        self._emoji_overlay_renderer.spawn(emoji)

    @property
    def peripheral_manager(self):
        return self.components.peripheral_manager

    def _resolve_display_mode(
        self, renderers: Sequence["StatefulBaseRenderer[Any]"]
    ) -> DeviceDisplayMode:
        return ComposedRenderer.required_display_mode(renderers)

    def render_frame(
        self,
        renderers: Sequence["StatefulBaseRenderer[Any]"],
    ) -> pygame.Surface | None:
        if self.components.display.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        if self.components.display.clock is None:
            raise RuntimeError("GameLoop clock is not initialized")
        display_mode = self._resolve_display_mode(renderers)
        self._reset_opengl_renderers_before_display_mode_change(display_mode)
        with self.components.display.display_mode(display_mode):
            return ComposedRenderer.render_batch(
                renderers,
                window=self.components.display,
                peripheral_manager=self.components.peripheral_manager,
                orientation=self.device.orientation,
            )

    def _reset_opengl_renderers_before_display_mode_change(
        self,
        display_mode: DeviceDisplayMode,
    ) -> None:
        current_mode = self.components.display.last_render_mode
        target_mode = display_mode.to_pygame_mode()
        if current_mode == target_mode:
            return
        for renderer in self._iter_runtime_renderers():
            if (
                renderer.initialized
                and renderer.device_display_mode == DeviceDisplayMode.OPENGL
            ):
                logger.info(
                    "Resetting OpenGL renderer %s before display mode transition",
                    renderer.name,
                )
                renderer.reset()

    def _iter_runtime_renderers(self) -> Sequence["StatefulBaseRenderer[Any]"]:
        seen: set[int] = set()
        result: list["StatefulBaseRenderer[Any]"] = []

        def visit(renderer: "StatefulBaseRenderer[Any]") -> None:
            renderer_id = id(renderer)
            if renderer_id in seen:
                return
            seen.add(renderer_id)
            result.append(renderer)
            if isinstance(renderer, ComposedRenderer):
                for child in renderer.renderers:
                    visit(child)
            elif isinstance(renderer, MultiScene):
                for scene in renderer.scenes:
                    visit(scene)

        if self._temporary_renderer is not None:
            visit(self._temporary_renderer)
        if self._emoji_overlay_renderer is not None:
            visit(self._emoji_overlay_renderer)

        game_modes = self.components.game_modes
        if game_modes._state is not None:
            for entry in game_modes.state.entries:
                visit(entry.title_renderer)
                visit(entry.renderer)
            for post_processor in game_modes.state.post_processors:
                visit(post_processor)

        return result

    def _prepare_container(
        self,
        *,
        device: Device,
        resolver: RuntimeContainer | None,
    ) -> RuntimeContainer:
        if resolver is None:
            return build_runtime_container(device=device)
        configure_runtime_container(
            container=resolver,
            device=device,
        )
        return resolver

    def _load_components(self) -> GameLoopComponents:
        return self.context_container.resolve(GameLoopComponents)

    def _preprocess_setup(self) -> None:
        self._dim_display()

    def _set_singleton(self) -> None:
        active_loop = self.get_game_loop()
        if active_loop is None:
            GameLoop.set_game_loop(self)
        elif active_loop is not self:
            logger.debug(
                "GameLoop initialized alongside existing instance; keeping original active"
            )

    def _initialize_screen(self) -> None:
        logger.info("Initializing display surfaces.")
        if (
            self.components.display.screen is None
            or self.components.display.clock is None
        ):
            self.components.display.initialize()
        logger.info("Binding initialized display surfaces to the device.")
        self.set_screen(self.components.display.screen)
        self.set_clock(self.components.display.clock)
        logger.info("Display surfaces are ready.")

    def ensure_screen_initialized(self) -> None:
        if (
            self.components.display.screen is None
            or self.components.display.clock is None
        ):
            self._initialize_screen()

    def _initialize(self) -> None:
        logger.info("Registering active GameLoop instance.")
        self._set_singleton()
        logger.info("Preparing display initialization.")
        self._initialize_screen()
        logger.info("Preparing peripheral detection.")
        self.components.peripheral_runtime.detect_and_start()
        logger.info("Peripheral detection complete.")
        self.initialized = True

    def _dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        if self.components.display.screen is not None:
            self.components.display.screen.fill("black")

    def _ensure_initialized(self) -> None:
        if self.initialized:
            return
        self._initialize()

    def _initialize_game_modes(self) -> None:
        self.components.display.ensure_initialized()
        logger.info("Initializing game mode components.")
        self.components.game_modes.initialize(
            window=self.components.display,
            peripheral_manager=self.components.peripheral_manager,
            orientation=self.device.orientation,
        )

    def _ensure_display_initialized(self) -> None:
        self.components.display.ensure_initialized()

    def _active_temporary_renderer(self) -> "StatefulBaseRenderer[Any]" | None:
        renderer = self._temporary_renderer
        deadline = self._temporary_renderer_deadline_monotonic
        if renderer is None or deadline is None:
            return None

        if time.monotonic() >= deadline:
            self._clear_temporary_renderer()
            return None

        if not renderer.initialized:
            self._ensure_display_initialized()
            renderer.initialize(
                window=self.components.display,
                peripheral_manager=self.components.peripheral_manager,
                orientation=self.device.orientation,
            )

        return renderer

    def _clear_temporary_renderer(self) -> None:
        renderer = self._temporary_renderer
        self._temporary_renderer = None
        self._temporary_renderer_deadline_monotonic = None
        if renderer is not None:
            renderer.reset()

    def _active_emoji_overlay_renderer(self) -> FloatingEmojiOverlayRenderer | None:
        renderer = self._emoji_overlay_renderer
        if renderer is None:
            return None
        if not renderer.has_active_emojis():
            self._emoji_overlay_renderer = None
            renderer.reset()
            return None
        return renderer

    def _maybe_log_perf_frame(
        self,
        *,
        renderers: Sequence["StatefulBaseRenderer[Any]"],
        timings: dict[str, float],
    ) -> None:
        if not _env_flag_enabled(PERF_LOG_ENABLED_ENV_VAR):
            return

        now = time.monotonic()
        interval = max(
            0.1,
            _env_float(
                PERF_LOG_INTERVAL_ENV_VAR,
                DEFAULT_PERF_LOG_INTERVAL_SECONDS,
            ),
        )
        if now < self._last_perf_log_monotonic + interval:
            return
        self._last_perf_log_monotonic = now

        renderer_names = ",".join(renderer.name for renderer in renderers) or "none"
        lifecycle_counts = self._renderer_lifecycle_counts()
        clock = self.components.display.clock
        fps = clock.get_fps() if clock is not None else 0.0

        logger.info(
            "render.perf.frame frame=%s fps=%.1f max_fps=%s total=%.2fms "
            "pre_tick=%.2fms events=%.2fms preprocess=%.2fms select=%.2fms "
            "render=%.2fms post=%.2fms blit=%.2fms flip=%.2fms "
            "device=%.2fms pacing=%.2fms post_tick=%.2fms publish=%.2fms "
            "renderers=%s active_initialized=%s all_initialized=%s "
            "post_processors=%s gc=%s rss=%s",
            self._frame_index,
            fps,
            self.max_fps,
            timings.get("total_ms", 0.0),
            timings.get("peripheral_pre_ms", 0.0),
            timings.get("events_ms", 0.0),
            timings.get("preprocess_ms", 0.0),
            timings.get("select_ms", 0.0),
            timings.get("render_ms", 0.0),
            timings.get("post_ms", 0.0),
            timings.get("blit_ms", 0.0),
            timings.get("flip_ms", 0.0),
            timings.get("device_ms", 0.0),
            timings.get("pacing_ms", 0.0),
            timings.get("peripheral_post_ms", 0.0),
            timings.get("clock_publish_ms", 0.0),
            renderer_names,
            sum(1 for renderer in renderers if renderer.initialized),
            lifecycle_counts["initialized"],
            len(self.components.game_modes.get_post_processors()),
            gc.get_count(),
            self._resident_memory_usage(),
        )

    def _renderer_lifecycle_counts(self) -> dict[str, int]:
        seen: set[int] = set()
        renderers: list["StatefulBaseRenderer[Any]"] = []
        if self.components.game_modes.initialized:
            for entry in self.components.game_modes.state.entries:
                renderers.extend(
                    self._collect_renderer_tree(entry.title_renderer, seen=seen)
                )
                renderers.extend(self._collect_renderer_tree(entry.renderer, seen=seen))
            for renderer in self.components.game_modes.get_post_processors():
                renderers.extend(self._collect_renderer_tree(renderer, seen=seen))
        return {
            "total": len(renderers),
            "initialized": sum(1 for renderer in renderers if renderer.initialized),
        }

    def _collect_renderer_tree(
        self,
        renderer: "StatefulBaseRenderer[Any]",
        *,
        seen: set[int],
    ) -> list["StatefulBaseRenderer[Any]"]:
        renderer_id = id(renderer)
        if renderer_id in seen:
            return []
        seen.add(renderer_id)

        result = [renderer]
        for child in getattr(renderer, "renderers", ()):
            result.extend(self._collect_renderer_tree(child, seen=seen))
        for child in getattr(renderer, "scenes", ()):
            result.extend(self._collect_renderer_tree(child, seen=seen))
        return result

    @staticmethod
    def _resident_memory_usage() -> int | None:
        if resource is None:
            return None
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    def _run_main_loop(self) -> None:
        if self.components.display.clock is None:
            raise RuntimeError("GameLoop failed to initialize display clock")
        handle_events = not is_pi()

        while self.running:
            frame_started_at = time.perf_counter()
            timings: dict[str, float] = {}

            step_started_at = time.perf_counter()
            self.components.peripheral_runtime.tick()
            timings["peripheral_pre_ms"] = _elapsed_ms_since(step_started_at)

            step_started_at = time.perf_counter()
            if handle_events:
                self.running = self.components.event_handler.handle_events()
            timings["events_ms"] = _elapsed_ms_since(step_started_at)

            step_started_at = time.perf_counter()
            self._preprocess_setup()  # can't dim display each time
            timings["preprocess_ms"] = _elapsed_ms_since(step_started_at)

            step_started_at = time.perf_counter()
            renderers = self._select_renderers()
            timings["select_ms"] = _elapsed_ms_since(step_started_at)

            timings.update(self._one_loop(renderers=renderers))
            # self._render_pacer.pace(render_start, 20)

            step_started_at = time.perf_counter()
            self.components.display.clock.tick(self.max_fps)
            timings["pacing_ms"] = _elapsed_ms_since(step_started_at)

            step_started_at = time.perf_counter()
            self.components.peripheral_runtime.tick()
            timings["peripheral_post_ms"] = _elapsed_ms_since(step_started_at)

            step_started_at = time.perf_counter()
            self.components.peripheral_manager.clock.on_next(
                self.components.display.clock
            )
            timings["clock_publish_ms"] = _elapsed_ms_since(step_started_at)

            self._frame_index += 1
            timings["total_ms"] = _elapsed_ms_since(frame_started_at)
            self._observe_frame_pipeline_pressure(timings)
            self._maybe_log_perf_frame(renderers=renderers, timings=timings)

    def _observe_frame_pipeline_pressure(
        self,
        timings: dict[str, float],
    ) -> None:
        frame_budget_ms = 1000.0 / self.max_fps
        work_ms = max(
            0.0,
            timings.get("total_ms", 0.0) - timings.get("pacing_ms", 0.0),
        )
        is_under_pressure = work_ms > frame_budget_ms
        if is_under_pressure == self._frame_pipeline_under_pressure:
            return
        self._frame_pipeline_under_pressure = is_under_pressure
        self._pipeline_lifecycle.emit(
            (
                HeartLifecycleKind.FRAME_PIPELINE_PRESSURE
                if is_under_pressure
                else HeartLifecycleKind.FRAME_PIPELINE_RECOVERED
            ),
            "game-loop",
            (
                HeartLifecycleReason.CAPACITY
                if is_under_pressure
                else HeartLifecycleReason.RECOVERED
            ),
            detail=(
                f"work_ms={work_ms:.3f};budget_ms={frame_budget_ms:.3f}"
            ),
        )
