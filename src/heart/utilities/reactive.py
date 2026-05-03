"""Heart-owned reactive stream boundary.

This module intentionally wraps the current RX backend so peripheral and
renderer APIs can depend on Heart stream names instead of backend modules.
"""
from __future__ import annotations

from typing import TypeAlias

try:
    import manyfold._rx as _rx_backend
    from manyfold._rx import Observable, Subject, operators, pipe
    from manyfold._rx.abc import DisposableBase, ObserverBase, SchedulerBase
    from manyfold._rx.disposable import CompositeDisposable, Disposable
    from manyfold._rx.scheduler import (EventLoopScheduler, NewThreadScheduler,
                                        ThreadPoolScheduler, TimeoutScheduler)
    from manyfold._rx.subject import BehaviorSubject
    from manyfold._rx.testing.marbles import marbles_testing
    from manyfold._rx.typing import StartableTarget
except ModuleNotFoundError:
    import manyfold.rx as _rx_backend
    from manyfold.rx import Observable, Subject, operators, pipe
    from manyfold.rx.abc import DisposableBase, ObserverBase, SchedulerBase
    from manyfold.rx.disposable import CompositeDisposable, Disposable
    from manyfold.rx.scheduler import (EventLoopScheduler, NewThreadScheduler,
                                       ThreadPoolScheduler, TimeoutScheduler)
    from manyfold.rx.subject import BehaviorSubject
    from manyfold.rx.testing.marbles import marbles_testing
    from manyfold.rx.typing import StartableTarget

ObservableStream: TypeAlias = Observable
SubjectStream: TypeAlias = Subject
BehaviorSubjectStream: TypeAlias = BehaviorSubject
DisposableHandle: TypeAlias = Disposable
CompositeDisposableHandle: TypeAlias = CompositeDisposable

create = _rx_backend.create
empty = _rx_backend.empty
from_iterable = _rx_backend.from_iterable
interval = _rx_backend.interval
just = _rx_backend.just
merge = _rx_backend.merge
combine_latest = _rx_backend.combine_latest
ops = operators

__all__ = [
    "BehaviorSubject",
    "BehaviorSubjectStream",
    "CompositeDisposable",
    "CompositeDisposableHandle",
    "Disposable",
    "DisposableBase",
    "DisposableHandle",
    "EventLoopScheduler",
    "NewThreadScheduler",
    "Observable",
    "ObservableStream",
    "ObserverBase",
    "SchedulerBase",
    "StartableTarget",
    "Subject",
    "SubjectStream",
    "ThreadPoolScheduler",
    "TimeoutScheduler",
    "combine_latest",
    "create",
    "empty",
    "from_iterable",
    "interval",
    "just",
    "merge",
    "marbles_testing",
    "operators",
    "ops",
    "pipe",
]
