"""Internal helpers for renderer performance features."""

from . import frame_accumulator as _frame_accumulator

FrameAccumulator = _frame_accumulator.FrameAccumulator

del _frame_accumulator
