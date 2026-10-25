"""Compute an answer in the background as soon as a spot is dealt, and cache it.

Used by the equity drill and the PLO nuts drill: both take up to a couple of
seconds to grade, so the work starts while the user is still thinking.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class BackgroundCache(Generic[K, V]):
    def __init__(self, compute: Callable[[K], V], *, workers: int = 2, size: int = 256, name: str = "bg"):
        self._compute = compute
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)
        self._cache: OrderedDict[K, Future] = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def start(self, key: K) -> Future:
        with self._lock:
            fut = self._cache.get(key)
            if fut is None:
                fut = self._pool.submit(self._compute, key)
                self._cache[key] = fut
                while len(self._cache) > self._size:
                    self._cache.popitem(last=False)
            else:
                self._cache.move_to_end(key)
            return fut

    def get(self, key: K) -> V:
        return self.start(key).result()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
