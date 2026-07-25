from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Any, cast

from manyfold import CompositeSubscription, Subscribable
from manyfold.architecture import PubSubTopic

from heart.peripheral.core.input.streams import map_stream, stream_from

NAVIGATION_TOPIC = "heart.input.navigation"
HEART_INPUT_PUBSUB = "heart"


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


@dataclass(frozen=True, slots=True)
class NavigationEvent:
    kind: str
    source: str
    step: int


class NavigationProfile:
    def __init__(self, intents: Subscribable[NavigationIntent]) -> None:
        self._topic = PubSubTopic(
            NAVIGATION_TOPIC,
            schema=NavigationEvent,
            pubsub=HEART_INPUT_PUBSUB,
        )
        self._source_subscription = intents.subscribe(self._publish)

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
    def intents(self) -> Subscribable[NavigationIntent]:
        return stream_from(self._topic.map(_intent_from_row))

    @cached_property
    def browse(self) -> Subscribable[BrowseIntent]:
        return cast(
            Subscribable[BrowseIntent],
            self.intents.filter(lambda intent: isinstance(intent, BrowseIntent)),
        )

    @cached_property
    def activate(self) -> Subscribable[ActivateIntent]:
        return cast(
            Subscribable[ActivateIntent],
            self.intents.filter(lambda intent: isinstance(intent, ActivateIntent)),
        )

    @cached_property
    def alternate_activate(self) -> Subscribable[AlternateActivateIntent]:
        return cast(
            Subscribable[AlternateActivateIntent],
            self.intents.filter(
                lambda intent: isinstance(intent, AlternateActivateIntent)
            ),
        )

    @cached_property
    def browse_delta(self) -> Subscribable[int]:
        return map_stream(self.browse, lambda intent: intent.step)

    def inject_browse(self, step: int, source: str = "beats.control") -> None:
        if step == 0:
            return
        self._publish(BrowseIntent(source=source, step=step))

    def inject_activate(self, source: str = "beats.control") -> None:
        self._publish(ActivateIntent(source=source))

    def inject_alternate_activate(self, source: str = "beats.control") -> None:
        self._publish(AlternateActivateIntent(source=source))

    def close(self) -> None:
        self._source_subscription.dispose()

    def _publish(self, intent: NavigationIntent) -> None:
        if isinstance(intent, BrowseIntent):
            event = NavigationEvent(
                kind="browse", source=intent.source, step=intent.step
            )
        elif isinstance(intent, ActivateIntent):
            event = NavigationEvent(kind="activate", source=intent.source, step=0)
        else:
            event = NavigationEvent(
                kind="alternate_activate",
                source=intent.source,
                step=0,
            )
        self._topic.publish(event)


def _intent_from_row(row: Any) -> NavigationIntent:
    kind = str(row.kind)
    source = str(row.source)
    if kind == "browse":
        return BrowseIntent(source=source, step=int(row.step))
    if kind == "activate":
        return ActivateIntent(source=source)
    if kind == "alternate_activate":
        return AlternateActivateIntent(source=source)
    raise ValueError(f"Unknown navigation event kind {kind!r}")
