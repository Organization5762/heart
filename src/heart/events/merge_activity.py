"""Helpers for instrumenting renderer surface merges with time-decayed metrics."""

from __future__ import annotations

import contextlib
import functools
from types import MethodType
from typing import Callable, Generator, Iterable, Protocol

from heart.events.metrics import TimeDecayedActivity


class SupportsMergeSurfaces(Protocol):
    """Protocol capturing the subset of :class:`GameLoop` required for instrumentation."""

    renderer_variant: object

    def merge_surfaces(self, surface1: object, surface2: object) -> object:
        """Merge two renderer surfaces and return the resulting surface."""


Labeler = Callable[[SupportsMergeSurfaces], Iterable[tuple[str, float]]]


def _default_labeler(loop: SupportsMergeSurfaces) -> Iterable[tuple[str, float]]:
    """Return merge metric keys covering overall and variant-specific activity."""

    variant = getattr(loop, "renderer_variant", None)
    suffix: str | None = None
    if variant is None:
        suffix = None
    else:
        name = getattr(variant, "name", None)
        if isinstance(name, str):
            suffix = name.lower()
        else:
            value = getattr(variant, "value", None)
            suffix = str(value).lower() if value is not None else str(variant).lower()

    keys: list[tuple[str, float]] = [("merge.activity", 1.0)]
    if suffix:
        keys.append((f"merge.activity.variant.{suffix}", 1.0))
    return keys


@contextlib.contextmanager
def track_merge_activity(
    loop: SupportsMergeSurfaces,
    metric: TimeDecayedActivity[str],
    *,
    labeler: Labeler | None = None,
) -> Generator[None, None, None]:
    """Record time-decayed activity whenever ``loop.merge_surfaces`` executes.

    Parameters
    ----------
    loop:
        Instance exposing a ``merge_surfaces`` method compatible with the
        :class:`GameLoop` API.
    metric:
        The :class:`~heart.events.metrics.TimeDecayedActivity` instance used to
        capture merge activity.
    labeler:
        Optional callable returning ``(key, weight)`` pairs for each observation.
        When omitted, observations are recorded against ``"merge.activity"`` and
        a variant-specific key derived from ``loop.renderer_variant``.

    Yields
    ------
    ``None``
        Ensures the caller can scope the instrumentation with a ``with`` block.

    Notes
    -----
    ``track_merge_activity`` temporarily replaces ``loop.merge_surfaces`` and
    restores the original method when the context exits, even when exceptions are
    raised within the managed block.  The wrapper is bound to ``loop`` so the
    instrumentation is isolated to the provided instance.
    """

    bound_original = loop.merge_surfaces

    def _label_pairs() -> Iterable[tuple[str, float]]:
        if labeler is None:
            return _default_labeler(loop)
        return labeler(loop)

    @functools.wraps(bound_original)
    def instrumented(self: SupportsMergeSurfaces, surface1: object, surface2: object) -> object:
        for key, weight in _label_pairs():
            metric.observe(key, value=weight)
        return bound_original(surface1, surface2)

    setattr(loop, "merge_surfaces", MethodType(instrumented, loop))
    try:
        yield
    finally:
        setattr(loop, "merge_surfaces", bound_original)
