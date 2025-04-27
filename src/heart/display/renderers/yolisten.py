import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


class YoListenRenderer(BaseRenderer):
    def __init__(
        self,
        font: str = "Arial Black",  # Changed to Arial Black which is bolder
        font_weight: int = 900,  # Increased font weight to maximum
        font_size: int = 20,  # Increased font size slightly
        color: Color = Color(255, 0, 0),  # Red color
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.color = color
        self.font_name = font
        self.base_font_size = font_size
        self.initialized = False
        self.words = ["YO", "LISTEN", "Y'HEAR", "THAT"]
        self.screen_count = 4

        # Animation state
        self.scaled_fonts = {}
        self.last_flash_time = 0
        self.flash_delay = 100  # ms between flashes

    def _initialize(self) -> None:
        # Pre-calculate scaled fonts for each word
        for word in self.words:
            self.scaled_fonts[word] = self._get_scaled_font(word)
        self.initialized = True

    def _get_scaled_font(self, word: str) -> pygame.font.Font:
        # Start with base font size
        font_size = self.base_font_size
        font = pygame.font.SysFont(self.font_name, font_size)

        # Get the text size
        text_width, _ = font.size(word)

        # Scale down if too wide
        while text_width > 64:  # Assuming 64 is the screen width
            font_size -= 1
            font = pygame.font.SysFont(self.font_name, font_size)
            text_width, _ = font.size(word)

        return font

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.initialized:
            self._initialize()

        window_width, window_height = window.get_size()
        screen_width = window_width // self.screen_count

        # Clear the window
        window.fill((0, 0, 0))

        # Get rotation value to determine how many words to show
        rotation = (
            peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )

        # Calculate number of words to show and flash state
        base_words = min(max(0, rotation // 5), len(self.words))
        extra_rotation = max(0, rotation - (len(self.words) * 5))

        # Determine if we should show words based on flash timing
        current_time = pygame.time.get_ticks()
        should_show = True
        if base_words == len(self.words) and extra_rotation > 0:
            # Flash when all words are shown and rotating further
            flash_cycle = (current_time - self.last_flash_time) // self.flash_delay
            should_show = flash_cycle % 2 == 0
            if (current_time - self.last_flash_time) >= self.flash_delay:
                self.last_flash_time = current_time

        # Draw words if we should show them
        if should_show:
            words_to_show = self.words[:base_words]
            for i, word in enumerate(words_to_show):
                x_offset = i * screen_width
                y_offset = (window_height - self.scaled_fonts[word].get_linesize()) // 2
                text_surface = self.scaled_fonts[word].render(
                    word, True, self.color._as_tuple()
                )
                text_width, _ = text_surface.get_size()
                x_centered = x_offset + (screen_width - text_width) // 2
                screen_surface = window.subsurface(
                    pygame.Rect(x_offset, 0, screen_width, window_height)
                )
                screen_surface.blit(text_surface, (x_centered - x_offset, y_offset))
