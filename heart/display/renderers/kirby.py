from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
import pygame

class KirbySwimming(BaseRenderer):
    def __init__(self) -> None:
        self.initialized = False
        self.current_frame = 0

        self.key_frames = [
            (((x*24)+5), 0, 24, 24) for x in range(0, 11)
        ]

        self.time_since_last_update = None
        self.time_between_frames_ms = 500

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet("swimming.png")
        self.initialized = True

    def process(self, window, clock) -> None:
        if self.time_since_last_update is None or self.time_since_last_update > self.time_between_frames_ms:
            if not self.initialized:
                self._initialize()

            if self.current_frame >= len(self.key_frames) - 1:
                self.current_frame = 0
            else:
                self.current_frame += 1

            self.time_since_last_update = 0

        image = self.spritesheet.image_at(self.key_frames[self.current_frame])
        image = pygame.transform.scale(image, (120, 120))
        window.blit(image, (30, 30))

        self.time_since_last_update += clock.get_time()