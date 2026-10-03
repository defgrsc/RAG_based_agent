import copy
import hashlib
import json
import threading
import time
from typing import Any

from config import ANSWER_CACHE_MAX_ITEMS, ANSWER_CACHE_TTL_SECONDS, RAG_CACHE_MAX_ITEMS, RAG_CACHE_TTL_SECONDS


class TtlCache:
    def __init__(self, max_items: int, ttl_seconds: int):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None

            created_at, value = item
            if now - created_at > self.ttl_seconds:
                self._items.pop(key, None)
                return None

            return copy.deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        if self.max_items <= 0 or self.ttl_seconds <= 0:
            return

        with self._lock:
            if len(self._items) >= self.max_items:
                oldest_key = min(self._items, key=lambda item_key: self._items[item_key][0])
                self._items.pop(oldest_key, None)
            self._items[key] = (time.time(), copy.deepcopy(value))

    def delete_many(self, keys) -> int:
        with self._lock:
            deleted = 0
            for key in keys:
                if key in self._items:
                    self._items.pop(key, None)
                    deleted += 1
            return deleted

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"items": len(self._items), "max_items": self.max_items, "ttl_seconds": self.ttl_seconds}


def stable_key(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


answer_cache = TtlCache(ANSWER_CACHE_MAX_ITEMS, ANSWER_CACHE_TTL_SECONDS)
rag_cache = TtlCache(RAG_CACHE_MAX_ITEMS, RAG_CACHE_TTL_SECONDS)


def clear_all_caches() -> None:
    answer_cache.clear()
    rag_cache.clear()
