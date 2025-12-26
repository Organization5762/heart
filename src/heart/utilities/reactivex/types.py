from __future__ import annotations

from typing import Any, Protocol, TypeVar

import reactivex
from reactivex.disposable import Disposable

T_co = TypeVar("T_co", covariant=True)
DEFAULT_SUBSCRIBER_COUNT = 1


class ConnectableStream(Protocol[T_co]):
    def connect(self, scheduler: Any = None) -> Disposable: ...

    def subscribe(self, observer: Any = None, scheduler: Any = None) -> Disposable: ...

    def pipe(self, *operators: Any) -> reactivex.Observable[T_co]: ...

    def auto_connect(
        self, subscriber_count: int = DEFAULT_SUBSCRIBER_COUNT
    ) -> reactivex.Observable[T_co]: ...
