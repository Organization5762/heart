from dataclasses import dataclass

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400


@dataclass(frozen=True)
class HeartTitleScreenState:
    heart_up: bool = True
    elapsed_ms: float = 0.0

    def advance(self, frame_ms: float) -> "HeartTitleScreenState":
        elapsed_ms = self.elapsed_ms + frame_ms
        heart_up = self.heart_up

        if elapsed_ms > DEFAULT_TIME_BETWEEN_FRAMES_MS:
            elapsed_ms = 0.0
            heart_up = not heart_up

        return HeartTitleScreenState(heart_up=heart_up, elapsed_ms=elapsed_ms)
