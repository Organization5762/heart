from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeyState:
    pressed: bool = False
    held: bool = False
    last_change_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class _KeyboardEvent:
    key: int
    key_name: str
    state: KeyState
    timestamp_ms: float


@dataclass(frozen=True, slots=True)
class KeyPressedEvent(_KeyboardEvent):
    pass


@dataclass(frozen=True, slots=True)
class KeyHeldEvent(_KeyboardEvent):
    pass


@dataclass(frozen=True, slots=True)
class KeyReleasedEvent(_KeyboardEvent):
    pass


KeyboardEvent = KeyPressedEvent | KeyHeldEvent | KeyReleasedEvent
