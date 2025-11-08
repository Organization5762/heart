

class DeterministicClock:
    """Simple monotonic clock stub that advances when instructed."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def advance(self, delta: float) -> None:
        self._now += delta

    def monotonic(self) -> float:
        return self._now