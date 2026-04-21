import asyncio
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int = 20):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _make_key(self, *args: Any) -> str:
        return ":".join(str(a) for a in args)

    def get(self, key: str) -> Any | None:
        if key in self._store:
            ts, value = self._store[key]
            if time.time() - ts < self.ttl:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def clear(self) -> None:
        self._store.clear()
        self._locks.clear()
