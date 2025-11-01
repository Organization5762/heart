import enum
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pygame
from PIL import Image

from heart import DeviceDisplayMode
from heart.device import Device
from heart.display.renderers.flame import FlameRenderer
from heart.display.renderers.free_text import FreeTextRenderer
from heart.navigation import AppController, ComposedRenderer, MultiScene
from heart.peripheral.core import events
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.heart_rates import (
    current_bpms,
)
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.display.renderers import BaseRenderer

logger = get_logger(__name__)

ACTIVE_GAME_LOOP: "GameLoop" | None = None
RGBA_IMAGE_FORMAT = "RGBA"


class RendererVariant(enum.Enum):
    BINARY = "BINARY"
    ITERATIVE = "ITERATIVE"
    # TODO: Add more


class GameLoop:
    def __init__(
        self,
        device: Device,
        peripheral_manager: PeripheralManager,
        max_fps: int = 60,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.initalized = False
        self.device = device
        self.peripheral_manager = peripheral_manager

        self.max_fps = max_fps
        self.app_controller = AppController()
        self.clock: pygame.time.Clock | None = None
        self.screen: pygame.Surface | None = None
        self.renderer_variant = render_variant

        # jank slide animation state machine
        self.mode_change: tuple[int, int] = (0, 0)
        self._last_mode_offset = 0
        self._last_offset_on_change = 0
        self._current_offset_on_change = 0
        self.renderers_cache: list["BaseRenderer"] | None = None

        self.time_last_debugging_press: float | None = None

        self._active_mode_index = 0

        # Phone text display state
        self._phone_text_display_time: float | None = None
        self._phone_text_duration = 5.0  # Display phone text for 5 seconds
        self._phone_text_renderer: FreeTextRenderer | None = None

        # Lampe controller
        self.feedback_buffer: np.ndarray | None = None
        self.tmp_float: float | None = None
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
        while self.running:
            self._handle_events()
            self._preprocess_setup()

            # Check for phone text
            phone_text = self.peripheral_manager.get_phone_text()
            popped_text = phone_text.pop_text()
            if popped_text:
                # Set the time when text was received
                self._phone_text_display_time = time.time()
                # Create a text renderer for the phone text
                self._phone_text_renderer = FreeTextRenderer()

            # If we're in the phone text display period, add the text renderer
            renderers: list["BaseRenderer"]
            if self._phone_text_display_time is not None:
                current_time = time.time()
                if self._phone_text_renderer is None:
                    self._phone_text_renderer = FreeTextRenderer()
                renderers = [self._phone_text_renderer]
                if (
                    current_time - self._phone_text_display_time
                    > self._phone_text_duration
                ):
                    # Reset phone text display time after duration expires
                    self._phone_text_display_time = None

            else:
                renderers = self.app_controller.get_renderers(
                    peripheral_manager=self.peripheral_manager
                )

            # Check if the average BPM is above 80 and show flames if so
            if current_bpms and len(current_bpms) >= 5:
                bpm_values = [bpm for bpm in current_bpms.values() if bpm > 0]
                if bpm_values and sum(bpm_values) / len(bpm_values) > 150:
                    for r in renderers:
                        if hasattr(r, "is_flame_renderer") and r.is_flame_renderer:
                            break
                    else:
                        renderers.append(FlameRenderer())
            self._one_loop(renderers)
            clock.tick(self.max_fps)

        pygame.quit()

    def process_renderer(self, renderer: "BaseRenderer") -> pygame.Surface | None:
        try:
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

            renderer._internal_process(
                window=screen,
                clock=self.clock,
                peripheral_manager=self.peripheral_manager,
                orientation=self.device.orientation,
            )

            return screen
        except Exception as e:
            logger.error(f"Error processing renderer: {e}", exc_info=True)
            return None

    def __finalize_rendering(self, screen: pygame.Surface) -> Image.Image:
        image = pygame.surfarray.pixels3d(screen)

        # HACKKK
        bluetooth_switch = self.peripheral_manager.bluetooth_switch()
        if bluetooth_switch is not None:
            ###
            # Button One
            ###
            if (switch_one := bluetooth_switch.switch_one()) is not None:
                rotation_delta = switch_one.get_rotation_since_last_long_button_press()
                if rotation_delta != 0:
                    # 0.05 per detent, same feel as before
                    factor = 1.0 + 0.05 * rotation_delta
                    factor = max(
                        0.0, min(5.0, factor)
                    )  # allow full desat → heavy oversat

                    # ---------- saturation tweak (RGB → lerp with luminance) -------------
                    img = image.astype(np.float32)

                    # perceptual luma used by Rec. 601
                    lum = (
                        0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
                    )[..., None]  # shape (H, W, 1)

                    # interpolate: lum + factor × (color – lum)
                    img_sat = lum + factor * (img - lum)

                    image[:] = np.clip(img_sat, 0, 255).astype(np.uint8)

            ###
            # Button Two
            ###
            if self.tmp_float is None:
                self.tmp_float = np.empty_like(image, dtype=np.float32)
            if (hue_switch := bluetooth_switch.switch_two()) is not None:
                delta = hue_switch.get_rotation_since_last_long_button_press()
                if delta:
                    # 0.03 ~= ~11° per detent; tune to taste
                    hue_delta = (delta * 0.03) % 1.0
                    # Convert to HSV, roll H channel, convert back
                    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
                    hsv[..., 0] = (hsv[..., 0] / 179.0 + hue_delta) % 1.0 * 179.0
                    image[:] = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

            ###
            # Button Three
            ###
            if (edge_sw := bluetooth_switch.switch_three()) is not None:
                d = edge_sw.get_rotation_since_last_long_button_press()
                if d:  # ±10 % per detent
                    self.edge_thresh = int(
                        np.clip(self.edge_thresh * (1.0 + 0.10 * d), 1, 255)
                    )

                    # --- fast edge magnitude (same math as before) -----------------------------
                    lum = (
                        0.299 * image[..., 0]  # perceptual luminance
                        + 0.587 * image[..., 1]
                        + 0.114 * image[..., 2]
                    ).astype(np.int16)

                    gx = np.abs(np.roll(lum, -1, 1) - np.roll(lum, 1, 1))
                    gy = np.abs(np.roll(lum, -1, 0) - np.roll(lum, 1, 0))
                    edge_mag = gx + gy  # 0‥510

                    # --- convert to a *soft* alpha mask ----------------------------------------
                    #   • everything below threshold fades to 0
                    #   • values above threshold ramp smoothly toward 1
                    alpha = np.clip(
                        (edge_mag.astype(np.float32) - self.edge_thresh)
                        / (255 - self.edge_thresh),
                        0.0,
                        1.0,
                    )
                    alpha **= 0.5  # gamma-soften: 0.5 ≈ thicker, lighter lines
                    alpha = alpha[..., None]  # shape => (H,W,1) for RGB broadcasting

                    # --- composite: dim base layer, add white edges ----------------------------
                    base = image.astype(np.float32) * 0.75  # 25 % darker background
                    edges = alpha * 255.0  # white strokes
                    out = np.clip(base + edges, 0, 255)

                    image[:] = out.astype(np.uint8)

        # TODO: This operation will be slow.
        alpha = pygame.surfarray.pixels_alpha(screen)
        image = np.dstack((image, alpha))
        image = np.transpose(image, (1, 0, 2))
        image = Image.fromarray(image, RGBA_IMAGE_FORMAT)
        return image

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
        with ThreadPoolExecutor() as executor:
            surfaces: list[pygame.Surface] = [
                i
                for i in list(executor.map(self.process_renderer, renderers))
                if i is not None
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
        else:
            return None

    def _render_fn(self, override_renderer_variant: RendererVariant | None):
        variant = override_renderer_variant or self.renderer_variant
        match variant:
            case RendererVariant.BINARY:
                return self._render_surfaces_binary
            case RendererVariant.ITERATIVE:
                return self._render_surface_iterative

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
        image = self.__finalize_rendering(result) if result else None
        if image is not None:
            bytes = image.tobytes()
            surface = pygame.image.frombytes(bytes, image.size, image.mode)
            self.screen.blit(surface, (0, 0))

        if len(renderers) > 0:
            pygame.display.flip()
            # Convert screen to PIL Image
            image = pygame.surfarray.array3d(self.screen)
            image = np.transpose(image, (1, 0, 2))
            image = Image.fromarray(image)
            self.device.set_image(image)

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

    def _preprocess_setup(self):
        self.__dim_display()

    def __set_singleton(self) -> None:
        if self.get_game_loop() is not None:
            raise Exception("An active GameLoop exists already, please re-use that one")

        GameLoop.set_game_loop(self)

    def _initialize_screen(self) -> None:
        pygame.init()
        self.screen = pygame.Surface(self.device.full_display_size(), pygame.SHOWN)
        self.clock = pygame.time.Clock()

    def _initialize_peripherals(self) -> None:
        logger.info("Attempting to detect attached peripherals")
        self.peripheral_manager.detect()
        logger.info(
            f"Detected attached peripherals - found {len(self.peripheral_manager.peripheral)}. {self.peripheral_manager.peripheral=}"
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
