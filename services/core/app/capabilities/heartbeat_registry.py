from __future__ import annotations

from datetime import datetime


class CapabilityExecutorHeartbeatRegistry:
    def __init__(self) -> None:
        self._heartbeats: dict[str, datetime] = {}

    def clear(self) -> None:
        self._heartbeats.clear()

    def mark(self, executor: str, *, now: datetime) -> None:
        self._heartbeats[executor] = now

    def has_recent(self, executor: str, *, now: datetime, max_age_seconds: int) -> bool:
        heartbeat = self._heartbeats.get(executor)
        if heartbeat is None:
            return False
        age = (now - heartbeat).total_seconds()
        return age <= max(1, max_age_seconds)
