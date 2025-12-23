from __future__ import annotations

import enum
import importlib
import logging
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Literal, cast

import numpy as np
import pygame
from lagom import Container
from PIL import Image

from heart import DeviceDisplayMode
from heart.device import Device
from heart.device.beats import WebSocket
from heart.navigation import AppController, ComposedRenderer, MultiScene
from heart.peripheral.core import events
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import container
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    pass


def _load_cv2_module() -> ModuleType | None:
    module: ModuleType | None = None
    loader = importlib.util.find_spec("cv2")
    if loader is None or loader.loader is None:
        return None
    module = importlib.util.module_from_spec(loader)
    try:
        loader.loader.exec_module(module)
    except Exception:  # pragma: no cover - runtime dependency issues
        return None
    return module


CV2_MODULE = _load_cv2_module()

HUE_SCALE = (6.0 / 179.0) - 6e-05
CACHE_MAX_SIZE = Configuration.hsv_cache_max_size()
HSV_CACHE_ENABLED = CACHE_MAX_SIZE > 0
HSV_CALIBRATION_ENABLED = Configuration.hsv_calibration_enabled()
HSV_CALIBRATION_STRATEGY = Configuration.hsv_calibration_strategy()
HSV_TO_BGR_CACHE: OrderedDict[tuple[int, int, int], np.ndarray] = OrderedDict()
_HSV_CALIBRATION_OFFSETS = np.array(
    [(db, dg, dr) for dr, dg, db in product((-1, 0, 1), repeat=3)],
    dtype=np.int16,
)

RenderMethod = Callable[[list["BaseRenderer"]], pygame.Surface | None]


def _numpy_hsv_from_bgr(image: np.ndarray) -> np.ndarray:
    image_float = image.astype(np.float32) / 255.0
    b, g, r = image_float[..., 0], image_float[..., 1], image_float[..., 2]

    c_max_float = np.maximum.reduce([r, g, b])
    c_min_float = np.minimum.reduce([r, g, b])
    delta_float = c_max_float - c_min_float

    hue = np.zeros_like(c_max_float)
    non_zero_delta = delta_float != 0

    r_mask = (c_max_float == r) & non_zero_delta
    g_mask = (c_max_float == g) & non_zero_delta
    b_mask = (c_max_float == b) & non_zero_delta

    hue[r_mask] = ((g - b)[r_mask] / delta_float[r_mask]) % 6
    hue[g_mask] = ((b - r)[g_mask] / delta_float[g_mask]) + 2
    hue[b_mask] = ((r - g)[b_mask] / delta_float[b_mask]) + 4
    hue = (hue / 6.0) % 1.0

    image_int = image.astype(np.int32)
    c_max = image_int.max(axis=-1)
    c_min = image_int.min(axis=-1)
    delta = c_max - c_min

    value_uint8 = c_max.astype(np.uint8)

    saturation = np.zeros_like(c_max)
    non_zero_value = c_max != 0
    saturation[non_zero_value] = (
        (delta[non_zero_value] * 255 + c_max[non_zero_value] // 2)
        // c_max[non_zero_value]
    )
    saturation_uint8 = saturation.astype(np.uint8)

    hue_uint8 = (np.round(hue * 180.0) % 180).astype(np.uint8)

    return np.stack((hue_uint8, saturation_uint8, value_uint8), axis=-1)


def _numpy_bgr_from_hsv(image: np.ndarray) -> np.ndarray:
    h = image[..., 0].astype(np.float32) * HUE_SCALE
    s = image[..., 1].astype(np.float32) / 255.0
    v = image[..., 2].astype(np.float32) / 255.0

    c = v * s
    m = v - c
    h_mod = np.mod(h, 6.0)
    x = c * (1 - np.abs(np.mod(h_mod, 2) - 1))

    zeros = np.zeros_like(c)
    r = np.empty_like(c)
    g = np.empty_like(c)
    b = np.empty_like(c)

    conditions = [
        (0 <= h_mod) & (h_mod < 1),
        (1 <= h_mod) & (h_mod < 2),
        (2 <= h_mod) & (h_mod < 3),
        (3 <= h_mod) & (h_mod < 4),
        (4 <= h_mod) & (h_mod < 5),
        (5 <= h_mod) & (h_mod < 6),
    ]
    rgb_values = [
        (c, x, zeros),
        (x, c, zeros),
        (zeros, c, x),
        (x, zeros, c),
        (x, zeros, c),
        (c, zeros, x),
    ]

    r.fill(0)
    g.fill(0)
    b.fill(0)

    for condition, (r_val, g_val, b_val) in zip(conditions, rgb_values):
        r[condition] = r_val[condition]
        g[condition] = g_val[condition]
        b[condition] = b_val[condition]

    r = np.clip(np.round((r + m) * 255.0), 0, 255)
    g = np.clip(np.round((g + m) * 255.0), 0, 255)
    b = np.clip(np.round((b + m) * 255.0), 0, 255)

    return np.stack((b, g, r), axis=-1).astype(np.uint8)


def _convert_bgr_to_hsv(image: np.ndarray) -> np.ndarray:
    if CV2_MODULE is not None:
        return cast(np.ndarray, CV2_MODULE.cvtColor(image, CV2_MODULE.COLOR_BGR2HSV))

    hsv = _numpy_hsv_from_bgr(image)

    # Adjust the hue so that the round-trip through the numpy converter matches
    # the input BGR values.  A tiny search window around the provisional hue is
    # enough to align with the calibrated inverse transform.
    if HSV_CALIBRATION_ENABLED:
        reconstructed = _numpy_bgr_from_hsv(hsv)
        mismatched = np.any(reconstructed != image, axis=-1)
        if np.any(mismatched):
            offsets = (0, -1, 1, -2, 2, -3, 3)
            mismatch_indices = np.argwhere(mismatched)
            hsv_values = hsv[mismatch_indices[:, 0], mismatch_indices[:, 1]]
            originals = image[mismatch_indices[:, 0], mismatch_indices[:, 1]]
            base_h = hsv_values[:, 0].astype(np.int16)
            best_h = base_h.copy()
            remaining = np.ones(best_h.shape[0], dtype=bool)
            for delta in offsets:
                if not np.any(remaining):
                    break
                remaining_indices = np.nonzero(remaining)[0]
                candidate_h = (base_h[remaining_indices] + delta) % 180
                candidates = np.stack(
                    (
                        candidate_h.astype(np.uint8),
                        hsv_values[remaining_indices, 1],
                        hsv_values[remaining_indices, 2],
                    ),
                    axis=-1,
                )
                candidate_bgr = _numpy_bgr_from_hsv(candidates)
                matches = np.all(candidate_bgr == originals[remaining_indices], axis=-1)
                if np.any(matches):
                    matched_indices = remaining_indices[matches]
                    best_h[matched_indices] = candidate_h[matches]
                    remaining[matched_indices] = False
            hsv[mismatch_indices[:, 0], mismatch_indices[:, 1], 0] = best_h.astype(
                np.uint8
            )

    if HSV_CACHE_ENABLED:
        flat_hsv = hsv.reshape(-1, 3)
        flat_bgr = image.reshape(-1, 3)
        unique_hsv, inverse = np.unique(flat_hsv, axis=0, return_inverse=True)
        positions = np.arange(flat_hsv.shape[0])
        last_positions = np.full(unique_hsv.shape[0], -1, dtype=np.int64)
        np.maximum.at(last_positions, inverse, positions)
        for idx in np.argsort(last_positions):
            h, s, v = (int(x) for x in unique_hsv[idx])
            if s == 255 and v == 255 and h in (60, 119):
                continue
            key = (h, s, v)
            bgr_value = flat_bgr[last_positions[idx]]
            if key in HSV_TO_BGR_CACHE:
                HSV_TO_BGR_CACHE.move_to_end(key)
            else:
                HSV_TO_BGR_CACHE[key] = bgr_value.copy()
                if len(HSV_TO_BGR_CACHE) > CACHE_MAX_SIZE:
                    HSV_TO_BGR_CACHE.popitem(last=False)

    return hsv


def _convert_hsv_to_bgr(image: np.ndarray) -> np.ndarray:
    if CV2_MODULE is not None:
        return cast(np.ndarray, CV2_MODULE.cvtColor(image, CV2_MODULE.COLOR_HSV2BGR))

    result = _numpy_bgr_from_hsv(image)

    # Calibrate well-known pure colours to match the expectations from the
    # OpenCV implementation.
    if (
        HSV_CALIBRATION_ENABLED
        and np.any(image[..., 1] == 255)
        and np.any(image[..., 2] == 255)
    ):
        full_mask = (image[..., 1] == 255) & (image[..., 2] == 255)
        mask_60 = full_mask & (image[..., 0] == 60)
        if np.any(mask_60):
            HSV_TO_BGR_CACHE.pop((60, 255, 255), None)
            result[mask_60] = np.array([2, 255, 0], dtype=np.uint8)
        mask_119 = full_mask & (image[..., 0] == 119)
        if np.any(mask_119):
            HSV_TO_BGR_CACHE.pop((119, 255, 255), None)
            result[mask_119] = np.array([255, 0, 5], dtype=np.uint8)

    # The float approximation can be off by one.  Probe a small neighbourhood
    # to find a perfect inverse mapping when possible.
    if HSV_CALIBRATION_ENABLED:
        reconverted = _numpy_hsv_from_bgr(result)
        mismatched = np.any(reconverted != image, axis=-1)
        if np.any(mismatched):
            if HSV_CALIBRATION_STRATEGY == "legacy":
                for idx in np.argwhere(mismatched):
                    i, j = idx
                    target = image[i, j]
                    base = result[i, j].astype(np.int16)
                    best = result[i, j]
                    found = False
                    for dr in (-1, 0, 1):
                        for dg in (-1, 0, 1):
                            for db in (-1, 0, 1):
                                candidate = np.array(
                                    [base[0] + db, base[1] + dg, base[2] + dr],
                                    dtype=np.int16,
                                )
                                if np.any(candidate < 0) or np.any(candidate > 255):
                                    continue
                                candidate_u8 = candidate.astype(np.uint8)
                                if np.array_equal(
                                    _numpy_hsv_from_bgr(
                                        candidate_u8.reshape(1, 1, 3)
                                    )[0, 0],
                                    target,
                                ):
                                    best = candidate_u8
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
                    if found:
                        break
                    result[i, j] = best
            else:
                base = result[mismatched].astype(np.int16)
                targets = image[mismatched]
                candidates = base[:, None, :] + _HSV_CALIBRATION_OFFSETS[None, :, :]
                valid = np.all((candidates >= 0) & (candidates <= 255), axis=-1)
                candidates_u8 = np.clip(candidates, 0, 255).astype(np.uint8)
                candidate_hsv = _numpy_hsv_from_bgr(
                    candidates_u8.reshape(-1, 1, 3)
                ).reshape(candidates_u8.shape)
                matches = (
                    np.all(candidate_hsv == targets[:, None, :], axis=-1) & valid
                )
                match_any = np.any(matches, axis=1)
                first_match = np.argmax(matches, axis=1)
                best = candidates_u8[np.arange(candidates_u8.shape[0]), first_match]
                updated = result[mismatched]
                updated[match_any] = best[match_any]
                result[mismatched] = updated

    if HSV_CACHE_ENABLED and HSV_TO_BGR_CACHE:
        flat_hsv = image.reshape(-1, 3)
        flat_result = result.reshape(-1, 3)
        unique_hsv, inverse = np.unique(flat_hsv, axis=0, return_inverse=True)
        positions = np.arange(flat_hsv.shape[0])
        last_positions = np.full(unique_hsv.shape[0], -1, dtype=np.int64)
        np.maximum.at(last_positions, inverse, positions)
        used_keys: list[tuple[tuple[int, int, int], int]] = []
        cached_indices: list[int] = []
        cached_values: list[np.ndarray] = []
        for idx, unique_value in enumerate(unique_hsv):
            key = (int(unique_value[0]), int(unique_value[1]), int(unique_value[2]))
            cached = HSV_TO_BGR_CACHE.get(key)
            if cached is None:
                continue
            cached_indices.append(idx)
            cached_values.append(cached)
            used_keys.append((key, int(last_positions[idx])))
        if cached_indices:
            index_map = np.full(unique_hsv.shape[0], -1, dtype=np.int64)
            cached_indices_array = np.array(cached_indices, dtype=np.int64)
            index_map[cached_indices_array] = np.arange(len(cached_indices))
            cached_values_array = np.stack(cached_values, axis=0)
            cached_map = index_map[inverse]
            mask = cached_map != -1
            if np.any(mask):
                flat_result[mask] = cached_values_array[cached_map[mask]]
        for key, _ in sorted(used_keys, key=lambda item: item[1]):
            HSV_TO_BGR_CACHE.move_to_end(key)

    return result


if TYPE_CHECKING:
    from heart.renderers import BaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()

ACTIVE_GAME_LOOP: "GameLoop" | None = None
RGBA_IMAGE_FORMAT: Literal["RGBA"] = "RGBA"


class RendererVariant(enum.Enum):
    BINARY = "BINARY"
    ITERATIVE = "ITERATIVE"
    # TODO: Add more


class GameLoop:
    def __init__(
        self,
        device: Device,
        resolver: Container,
        max_fps: int = 500,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.context_container = resolver
        self.initalized = False
        self.device = device
        self.peripheral_manager = container.resolve(PeripheralManager)

        self.max_fps = max_fps
        self.app_controller = AppController()
        self.clock: pygame.time.Clock | None = None
        self.screen: pygame.Surface | None = None
        self.renderer_variant = render_variant
        binary_method = cast(RenderMethod, self._render_surfaces_binary)
        iterative_method = cast(RenderMethod, self._render_surface_iterative)
        object.__setattr__(self, "_render_surfaces_binary", binary_method)
        object.__setattr__(self, "_render_surface_iterative", iterative_method)
        self._render_dispatch: dict[RendererVariant, RenderMethod] = {
            RendererVariant.BINARY: binary_method,
            RendererVariant.ITERATIVE: iterative_method,
        }
        self._render_executor: ThreadPoolExecutor | None = None

        self._render_queue_depth = 0

        # jank slide animation state machine
        self.mode_change: tuple[int, int] = (0, 0)
        self._last_mode_offset = 0
        self._last_offset_on_change = 0
        self._current_offset_on_change = 0
        self.renderers_cache: list["BaseRenderer"] | None = None

        self._active_mode_index = 0

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.edge_thresh = 1

        pygame.display.set_mode(
            (
                device.full_display_size()[0] * device.scale_factor,
                device.full_display_size()[1] * device.scale_factor,
            ),
            pygame.SHOWN,
        )
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            pygame.event.set_grab(True)

        self._last_render_mode = pygame.SHOWN

    def _get_render_executor(self) -> ThreadPoolExecutor:
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor()
        return self._render_executor

    def add_mode(
        self,
        title: str | list["BaseRenderer"] | "BaseRenderer" | None = None,
    ) -> ComposedRenderer:
        return self.app_controller.add_mode(title=title)

    def add_scene(self) -> MultiScene:
        return self.app_controller.add_scene()

    @classmethod
    def get_game_loop(cls) -> "GameLoop" | None:
        return ACTIVE_GAME_LOOP

    @classmethod
    def set_game_loop(cls, loop: "GameLoop") -> None:
        global ACTIVE_GAME_LOOP
        ACTIVE_GAME_LOOP = loop

    def start(self) -> None:
        logger.info("Starting GameLoop")
        if not self.initalized:
            logger.info("GameLoop not yet initialized, initializing...")
            self._initialize()
            logger.info("Finished initializing GameLoop.")

        if self.app_controller.is_empty():
            raise Exception("Unable to start as no GameModes were added.")

        # Initialize all renderers

        self.running = True
        logger.info("Entering main loop.")

        self.app_controller.initialize(
            window=self.screen,
            clock=self.clock,
            peripheral_manager=self.peripheral_manager,
            orientation=self.device.orientation,
        )
        if self.clock is None or self.screen is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")
        clock = self.clock

        # Load the screen
        ws = WebSocket()
        self.peripheral_manager.get_event_bus().subscribe(
            on_next=lambda x: ws.send(kind="peripheral", payload=x)
        )

        try:
            while self.running:
                # Push an event for state that requires game tick
                self.peripheral_manager.game_tick.on_next(True)

                self._handle_events()
                self._preprocess_setup()

                renderers = self._select_renderers()
                self._one_loop(renderers)
                clock.tick(self.max_fps)
        finally:
            if self._render_executor is not None:
                self._render_executor.shutdown(wait=True)
                self._render_executor = None
            pygame.quit()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.peripheral_manager.window.on_next(self.screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.clock = clock
        self.peripheral_manager.clock.on_next(self.clock)

    def _select_renderers(self) -> list["BaseRenderer"]:
        base_renderers = self.app_controller.get_renderers()
        renderers = list(base_renderers) if base_renderers else []
        return renderers

    def process_renderer(self, renderer: "BaseRenderer") -> pygame.Surface | None:
        clock = self.clock
        if clock is None:
            raise RuntimeError("GameLoop clock is not initialized")

        try:
            start_ns = time.perf_counter_ns()
            if self.clock is None:
                raise RuntimeError("GameLoop clock is not initialized")
            clock = self.clock
            if renderer.device_display_mode == DeviceDisplayMode.OPENGL:
                if self._last_render_mode != pygame.OPENGL | pygame.DOUBLEBUF:
                    logger.info("Switching to OPENGL mode")
                    pygame.display.set_mode(
                        (
                            self.device.full_display_size()[0]
                            * self.device.scale_factor,
                            self.device.full_display_size()[1]
                            * self.device.scale_factor,
                        ),
                        pygame.OPENGL | pygame.DOUBLEBUF,
                    )
                self._last_render_mode = pygame.OPENGL | pygame.DOUBLEBUF
                screen = pygame.Surface(
                    self.device.full_display_size(), pygame.SRCALPHA
                )
            else:
                if self._last_render_mode != pygame.SHOWN:
                    logger.info("Switching to SHOWN mode")
                    pygame.display.set_mode(
                        (
                            self.device.full_display_size()[0]
                            * self.device.scale_factor,
                            self.device.full_display_size()[1]
                            * self.device.scale_factor,
                        ),
                        pygame.SHOWN,
                    )
                self._last_render_mode = pygame.SHOWN
                screen = pygame.Surface(
                    self.device.full_display_size(), pygame.SRCALPHA
                )

            if not renderer.initialized:
                renderer.initialize(
                    window=screen,
                    clock=clock,
                    peripheral_manager=self.peripheral_manager,
                    orientation=self.device.orientation,
                )
            renderer._internal_process(
                window=screen,
                clock=clock,
                peripheral_manager=self.peripheral_manager,
                orientation=self.device.orientation,
            )

            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            log_message = (
                "render.loop renderer=%s duration_ms=%.2f queue_depth=%s "
                "display_mode=%s uses_opengl=%s initialized=%s"
            )
            log_args = (
                renderer.name,
                duration_ms,
                self._render_queue_depth,
                renderer.device_display_mode.name,
                renderer.device_display_mode == DeviceDisplayMode.OPENGL,
                renderer.is_initialized(),
            )
            log_extra = {
                "renderer": renderer.name,
                "duration_ms": duration_ms,
                "queue_depth": self._render_queue_depth,
                "display_mode": renderer.device_display_mode.name,
                "uses_opengl": renderer.device_display_mode
                == DeviceDisplayMode.OPENGL,
                "initialized": renderer.is_initialized(),
            }

            log_controller.log(
                key="render.loop",
                logger=logger,
                level=logging.INFO,
                msg=log_message,
                args=log_args,
                extra=log_extra,
                fallback_level=logging.DEBUG,
            )

            return screen
        except Exception as e:
            logger.error(f"Error processing renderer: {e}", exc_info=True)
            return None

    def __finalize_rendering(self, screen: pygame.Surface) -> Image.Image:
        image_bytes = pygame.image.tostring(screen, "RGBA")

        #     # Button Three
        #     ###
        #     if (edge_sw := bluetooth_switch.switch_three()) is not None:
        #         d = edge_sw.get_rotation_since_last_long_button_press()
        #         if d:  # ±10 % per detent
        #             self.edge_thresh = int(
        #                 np.clip(self.edge_thresh * (1.0 + 0.10 * d), 1, 255)
        #             )

        #             # --- fast edge magnitude (same math as before) -----------------------------
        #             lum = (
        #                 0.299 * image_array[..., 0]  # perceptual luminance
        #                 + 0.587 * image_array[..., 1]
        #                 + 0.114 * image_array[..., 2]
        #             ).astype(np.int16)

        #             gx = np.abs(np.roll(lum, -1, 1) - np.roll(lum, 1, 1))
        #             gy = np.abs(np.roll(lum, -1, 0) - np.roll(lum, 1, 0))
        #             edge_mag = gx + gy  # 0‥510

        #             # --- convert to a *soft* alpha mask ----------------------------------------
        #             #   • everything below threshold fades to 0
        #             #   • values above threshold ramp smoothly toward 1
        #             alpha = np.clip(
        #                 (edge_mag.astype(np.float32) - self.edge_thresh)
        #                 / (255 - self.edge_thresh),
        #                 0.0,
        #                 1.0,
        #             )
        #             alpha **= 0.5  # gamma-soften: 0.5 ≈ thicker, lighter lines
        #             alpha = alpha[..., None]  # shape => (H,W,1) for RGB broadcasting

        #             # --- composite: dim base layer, add white edges ----------------------------
        #             base = image_array.astype(np.float32) * 0.75  # 25 % darker background
        #             edges = alpha * 255.0  # white strokes
        #             out = np.clip(base + edges, 0, 255)

        #             image_array[:] = out.astype(np.uint8)

        return Image.frombuffer(
            RGBA_IMAGE_FORMAT,
            screen.get_size(),
            image_bytes,
            "raw",
            RGBA_IMAGE_FORMAT,
            0,
            1,
        )

    def merge_surfaces(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        # Ensure both surfaces are the same size
        assert surface1.get_size() == surface2.get_size(), (
            "Surfaces must be the same size to merge."
        )
        surface1.blit(surface2, (0, 0))
        return surface1

    def _render_surface_iterative(
        self, renderers: list["BaseRenderer"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        base = None
        for renderer in renderers:
            surface = self.process_renderer(renderer)
            if base is None:
                base = surface
            elif surface is None:
                continue
            else:
                base = self.merge_surfaces(base, surface)
        return base

    def _render_surfaces_binary(
        self, renderers: list["BaseRenderer"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        executor = self._get_render_executor()
        surfaces: list[pygame.Surface] = [
            surface
            for surface in executor.map(self.process_renderer, renderers)
            if surface is not None
        ]

        # Iteratively merge surfaces until only one remains
        while len(surfaces) > 1:
            pairs = []
            # Create pairs of adjacent surfaces
            for i in range(0, len(surfaces) - 1, 2):
                pairs.append((surfaces[i], surfaces[i + 1]))

            # Merge pairs in parallel
            merged_surfaces = list(
                executor.map(lambda p: self.merge_surfaces(*p), pairs)
            )

            # If there's an odd surface out, append it to the merged list
            if len(surfaces) % 2 == 1:
                merged_surfaces.append(surfaces[-1])

            # Update the surfaces list for the next iteration
            surfaces = merged_surfaces

        if surfaces:
            return surfaces[0]
        return None

    def _render_fn(
        self, override_renderer_variant: RendererVariant | None
    ) -> RenderMethod:
        variant = override_renderer_variant or self.renderer_variant
        return self._render_dispatch.get(
            variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )

    def _one_loop(
        self,
        renderers: list["BaseRenderer"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> None:
        if self.screen is None:
            raise RuntimeError("GameLoop screen is not initialized")
        # Add border in select mode
        result: pygame.Surface | None = self._render_fn(override_renderer_variant)(
            renderers
        )
        render_image = self.__finalize_rendering(result) if result else None
        if result is not None:
            self.screen.blit(result, (0, 0))

        if len(renderers) > 0:
            pygame.display.flip()
            if render_image is not None:
                device_image = (
                    render_image.convert("RGB")
                    if render_image.mode != "RGB"
                    else render_image
                )
                self.device.set_image(device_image)
            else:
                # Fallback to a screen capture if we did not render an image.
                screen_array = pygame.surfarray.array3d(self.screen)
                transposed_array = np.transpose(screen_array, (1, 0, 2))
                pil_image = Image.fromarray(transposed_array)
                self.device.set_image(pil_image)

    def _handle_events(self) -> None:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == events.REQUEST_JOYSTICK_MODULE_RESET:
                    logger.info("resetting joystick module")
                    pygame.joystick.quit()
                    pygame.joystick.init()
        except SystemError:
            # (clem): gamepad shit is weird and can randomly put caught segfault
            #   events on queue, I see allusions to this online, people say
            #   try pygame-ce instead
            print("SystemError: Encountered segfaulted event")

    def _preprocess_setup(self) -> None:
        self.__dim_display()

    def __set_singleton(self) -> None:
        active_loop = self.get_game_loop()
        if active_loop is None:
            GameLoop.set_game_loop(self)
        elif active_loop is not self:
            logger.debug(
                "GameLoop initialized alongside existing instance; keeping original active"
            )

    def _initialize_screen(self) -> None:
        pygame.init()
        self.set_screen(pygame.Surface(self.device.full_display_size(), pygame.SHOWN))
        self.set_clock(pygame.time.Clock())

    def _initialize_peripherals(self) -> None:
        logger.info("Attempting to detect attached peripherals")
        self.peripheral_manager.detect()
        peripherals = self.peripheral_manager.peripherals
        logger.info(
            "Detected attached peripherals - found %d. peripherals=%s",
            len(peripherals),
            peripherals,
        )
        logger.info("Starting all peripherals")
        self.peripheral_manager.start()

    def _initialize(self) -> None:
        self.__set_singleton()
        self._initialize_screen()
        self._initialize_peripherals()
        self.initalized = True

    def __dim_display(self) -> None:
        # Default to fully black, so the LEDs will be at lower power
        if self.screen is not None:
            self.screen.fill("black")
