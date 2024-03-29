from dataclasses import dataclass
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
import pygame

@dataclass
class KeyFrame:
    frame: tuple[int,int,int,int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

class KirbyRunning(BaseRenderer):
    def __init__(self) -> None:
        self.initialized = False
        self.current_frame = 0

        self.key_frames = [
            KeyFrame(
                (0,0,28,28),
            ),
            KeyFrame(
                (28,0,28,28)
            ),
            KeyFrame(
                (56,0,28,28),
                up=10,
                right=7
            ),
            KeyFrame(
                (84,0,28,28),
                up=20,
                right=4
            ),
            KeyFrame(
                (112,0,28,28),
                down=10,
                right=4
            ),
            KeyFrame(
                (112,0,28,28),
                down=10
            ),
            KeyFrame(
                (140,0,28,28),
                down=10
            )
        ]

        self.time_since_last_update = None
        self.time_between_frames_ms = 50

        self.x = 30
        self.y = 30

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
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

            # Movement happens here
            current_frame = self.key_frames[self.current_frame]
            self.y += current_frame.down
            self.y -= current_frame.up
            self.x -= current_frame.left
            self.x += current_frame.right

        image = self.spritesheet.image_at(self.key_frames[self.current_frame].frame)
        window.blit(image, (self.x, self.y))

        self.time_since_last_update += clock.get_time()