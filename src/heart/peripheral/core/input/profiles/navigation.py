from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

from manyfold import StreamNode
from manyfold.architecture import NewValues

from heart.peripheral.core.subscriptions import CompositeSubscription


@dataclass(frozen=True, slots=True)
class _NavigationIntent:
    source: str


@dataclass(frozen=True, slots=True)
class BrowseIntent(_NavigationIntent):
    step: int


@dataclass(frozen=True, slots=True)
class ActivateIntent(_NavigationIntent):
    pass


@dataclass(frozen=True, slots=True)
class AlternateActivateIntent(_NavigationIntent):
    pass


NavigationIntent = BrowseIntent | ActivateIntent | AlternateActivateIntent


class NavigationProfile:
    def __init__(
        self,
        intents: StreamNode[NavigationIntent],
        injected_intents: NewValues[NavigationIntent],
    ) -> None:
        self._intents = intents
        self._injected_intents = injected_intents

    def subscribe_events(
        self,
        *,
        on_browse: Callable[[BrowseIntent], None] | None = None,
        on_browse_delta: Callable[[int], None] | None = None,
        on_activate: Callable[[ActivateIntent], None] | None = None,
        on_alternate_activate: Callable[[AlternateActivateIntent], None] | None = None,
    ) -> CompositeSubscription:
        subscriptions = []
        if on_browse is not None:
            subscriptions.append(self.browse.subscribe(on_next=on_browse))
        if on_browse_delta is not None:
            subscriptions.append(self.browse_delta.subscribe(on_next=on_browse_delta))
        if on_activate is not None:
            subscriptions.append(self.activate.subscribe(on_next=on_activate))
        if on_alternate_activate is not None:
            subscriptions.append(
                self.alternate_activate.subscribe(on_next=on_alternate_activate)
            )
        return CompositeSubscription(subscriptions)

    @cached_property
    def intents(self) -> StreamNode[NavigationIntent]:
        return self._intents

    @cached_property
    def browse(self) -> StreamNode[BrowseIntent]:
        return self.intents.filter(lambda intent: isinstance(intent, BrowseIntent)).map(
            lambda intent: intent
        )

    @cached_property
    def activate(self) -> StreamNode[ActivateIntent]:
        return self.intents.filter(
            lambda intent: isinstance(intent, ActivateIntent)
        ).map(lambda intent: intent)

    @cached_property
    def alternate_activate(self) -> StreamNode[AlternateActivateIntent]:
        return self.intents.filter(
            lambda intent: isinstance(intent, AlternateActivateIntent)
        ).map(lambda intent: intent)

    @cached_property
    def browse_delta(self) -> StreamNode[int]:
        return self.browse.map(lambda intent: intent.step)

    def inject_browse(self, step: int, source: str = "beats.control") -> None:
        if step == 0:
            return
        self._injected_intents.emit(BrowseIntent(source=source, step=step))

    def inject_activate(self, source: str = "beats.control") -> None:
        self._injected_intents.emit(ActivateIntent(source=source))

    def inject_alternate_activate(self, source: str = "beats.control") -> None:
        self._injected_intents.emit(AlternateActivateIntent(source=source))
