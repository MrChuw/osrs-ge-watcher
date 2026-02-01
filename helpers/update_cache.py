import time
from datetime import timedelta
from typing import Any


class UpdateTracker:
    def __init__(
        self,
        ttl: float | timedelta,
        cleanup_interval: float | timedelta = timedelta(hours=1),
    ):
        self.ttl_seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else float(ttl)
        self.cleanup_seconds = (
            cleanup_interval.total_seconds() if isinstance(cleanup_interval, timedelta) else float(cleanup_interval)
        )

        self._cache: dict[str, dict[str, Any]] = {}
        self._last_cleanup = time.monotonic()

    def should_update(self, item_id: str, current_state: Any) -> bool:
        now = time.monotonic()

        if (now - self._last_cleanup) >= self.cleanup_seconds:
            self._cleanup(now)

        entry = self._cache.get(item_id)

        if entry is None:
            self._update_cache(item_id, current_state, now)
            return True

        if entry["state"] != current_state or (now - entry["last_sent"]) >= self.ttl_seconds:
            self._update_cache(item_id, current_state, now)
            return True

        return False

    def _cleanup(self, now: float):
        threshold = max(self.ttl_seconds * 2, self.cleanup_seconds)
        self._cache = {k: v for k, v in self._cache.items() if (now - v["last_sent"]) <= threshold}
        self._last_cleanup = now

    def _update_cache(self, item_id: str, state: Any, timestamp: float):
        self._cache[item_id] = {
            "state": state,
            "last_sent": timestamp,
        }
