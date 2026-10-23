"""Minimal synchronous event bus."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def subscribe(self, event: str, fn: Callable[..., Any]) -> Callable[[], None]:
        self._subs[event].append(fn)

        def unsubscribe() -> None:
            if fn in self._subs[event]:
                self._subs[event].remove(fn)

        return unsubscribe

    def emit(self, event: str, **payload: Any) -> int:
        n = 0
        for fn in list(self._subs.get(event, ())):
            fn(**payload)
            n += 1
        return n
