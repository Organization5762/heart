from __future__ import annotations

from typing import Any, Protocol, TypeVar

import reactivex
from reactivex.disposable import Disposable

T_co = TypeVar("T_co", covariant=True)


class ConnectableStream(Protocol[T_co]):
    def connect(self, scheduler: Any = None) -> Disposable: ...

    def subscribe(self, observer: Any = None, scheduler: Any = None) -> Disposable: ...

    def pipe(self, *operators: Any) -> reactivex.Observable[T_co]: ...

    def auto_connect(self, subscriber_count: int = 1) -> reactivex.Observable[T_co]: ...
