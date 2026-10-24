"""In-process result cache bounded by total size and entry age."""

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Entry[V]:
    value: V
    size: int
    expires_at: float


class BoundedTTLCache[K, V]:
    """LRU cache whose estimated total size never exceeds max_bytes.

    Expired entries are dropped when read or when evicted for space.
    PRODUCTION: a shared cache (e.g. Redis with maxmemory + allkeys-lru) would replace this.
    """

    def __init__(
        self,
        max_bytes: int,
        ttl_seconds: float,
        size_of: Callable[[K, V], int],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_bytes = max_bytes
        self._ttl_seconds = ttl_seconds
        self._size_of = size_of
        self._clock = clock
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._total_bytes = 0

    def get(self, key: K) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._remove(key)
            return None
        self._entries.move_to_end(key)
        return entry.value

    def put(self, key: K, value: V) -> None:
        size = self._size_of(key, value)
        if size > self._max_bytes:
            return
        if key in self._entries:
            self._remove(key)
        self._entries[key] = _Entry(value, size, self._clock() + self._ttl_seconds)
        self._total_bytes += size
        while self._total_bytes > self._max_bytes:
            self._remove(next(iter(self._entries)))

    def _remove(self, key: K) -> None:
        self._total_bytes -= self._entries.pop(key).size
