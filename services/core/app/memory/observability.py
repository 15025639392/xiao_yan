from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Iterable

RETRIEVAL_P95_ALERT_THRESHOLD_MS = 120.0
CHAT_P95_ALERT_THRESHOLD_MS = 1500.0
WRITE_FAILURE_RATE_ALERT_THRESHOLD = 0.01
RETRIEVAL_HIT_RATE_ALERT_THRESHOLD = 0.4

# Grey-release runs often use 10~20 requests. We keep alert evaluation gated by
# a minimum sample size to reduce single-outlier noise during early rollout.
MIN_SAMPLES_FOR_LATENCY_ALERT = 20
MIN_SAMPLES_FOR_WRITE_ALERT = 20
MIN_SAMPLES_FOR_QUALITY_ALERT = 20


def _safe_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    return round(value, 3)


def _safe_average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


class KnowledgeObservabilityTracker:
    """Tracks MemPalace baseline observability metrics for chat flows."""

    def __init__(self, *, max_samples: int = 500) -> None:
        self._max_samples = max(20, int(max_samples))
        self._lock = Lock()
        self._retrieval_latencies_ms: deque[float] = deque(maxlen=self._max_samples)
        self._chat_latencies_ms: deque[float] = deque(maxlen=self._max_samples)
        self._retrieval_queries = 0
        self._retrieval_failures = 0
        self._retrieval_hit_queries = 0
        self._retrieval_hits_total = 0
        self._similarity_sum = 0.0
        self._similarity_count = 0
        self._write_attempts = 0
        self._write_failures = 0
        self._updated_at: datetime | None = None

    def record_retrieval(
        self,
        *,
        latency_ms: float,
        hit_count: int,
        similarity_scores: Iterable[float] | None = None,
        failed: bool = False,
    ) -> None:
        with self._lock:
            self._retrieval_queries += 1
            self._retrieval_latencies_ms.append(max(0.0, float(latency_ms)))
            if failed:
                self._retrieval_failures += 1
            if hit_count > 0:
                self._retrieval_hit_queries += 1
                self._retrieval_hits_total += int(hit_count)
            if similarity_scores is not None:
                for score in similarity_scores:
                    try:
                        normalized = float(score)
                    except (TypeError, ValueError):
                        continue
                    self._similarity_sum += normalized
                    self._similarity_count += 1
            self._updated_at = datetime.now(timezone.utc)

    def record_chat_latency(self, latency_ms: float) -> None:
        with self._lock:
            self._chat_latencies_ms.append(max(0.0, float(latency_ms)))
            self._updated_at = datetime.now(timezone.utc)

    def record_write(self, *, success: bool) -> None:
        with self._lock:
            self._write_attempts += 1
            if not success:
                self._write_failures += 1
            self._updated_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        with self._lock:
            self._retrieval_latencies_ms.clear()
            self._chat_latencies_ms.clear()
            self._retrieval_queries = 0
            self._retrieval_failures = 0
            self._retrieval_hit_queries = 0
            self._retrieval_hits_total = 0
            self._similarity_sum = 0.0
            self._similarity_count = 0
            self._write_attempts = 0
            self._write_failures = 0
            self._updated_at = None

    def snapshot(self) -> dict:
        with self._lock:
            retrieval_values = list(self._retrieval_latencies_ms)
            chat_values = list(self._chat_latencies_ms)
            retrieval_p95 = _safe_percentile(retrieval_values, 0.95)
            chat_p95 = _safe_percentile(chat_values, 0.95)
            retrieval_hit_rate = (
                round(self._retrieval_hit_queries / self._retrieval_queries, 4)
                if self._retrieval_queries > 0
                else None
            )
            write_failure_rate = (
                round(self._write_failures / self._write_attempts, 4)
                if self._write_attempts > 0
                else None
            )
            avg_similarity = (
                round(self._similarity_sum / self._similarity_count, 4)
                if self._similarity_count > 0
                else None
            )

            alerts: list[str] = []
            if (
                len(retrieval_values) >= MIN_SAMPLES_FOR_LATENCY_ALERT
                and retrieval_p95 is not None
                and retrieval_p95 > RETRIEVAL_P95_ALERT_THRESHOLD_MS
            ):
                alerts.append("retrieval_p95_above_120ms")
            if (
                len(chat_values) >= MIN_SAMPLES_FOR_LATENCY_ALERT
                and chat_p95 is not None
                and chat_p95 > CHAT_P95_ALERT_THRESHOLD_MS
            ):
                alerts.append("chat_p95_above_1500ms")
            if (
                self._write_attempts >= MIN_SAMPLES_FOR_WRITE_ALERT
                and write_failure_rate is not None
                and write_failure_rate > WRITE_FAILURE_RATE_ALERT_THRESHOLD
            ):
                alerts.append("write_failure_rate_above_1pct")
            if (
                self._retrieval_queries >= MIN_SAMPLES_FOR_QUALITY_ALERT
                and retrieval_hit_rate is not None
                and retrieval_hit_rate < RETRIEVAL_HIT_RATE_ALERT_THRESHOLD
            ):
                alerts.append("retrieval_hit_rate_below_40pct")

            return {
                "window": {
                    "max_samples": self._max_samples,
                    "updated_at": self._updated_at.isoformat() if self._updated_at is not None else None,
                },
                "latency": {
                    "retrieval_ms": {
                        "count": len(retrieval_values),
                        "avg": _safe_average(retrieval_values),
                        "p50": _safe_percentile(retrieval_values, 0.5),
                        "p95": retrieval_p95,
                    },
                    "chat_ms": {
                        "count": len(chat_values),
                        "avg": _safe_average(chat_values),
                        "p50": _safe_percentile(chat_values, 0.5),
                        "p95": chat_p95,
                    },
                },
                "quality": {
                    "queries": self._retrieval_queries,
                    "failures": self._retrieval_failures,
                    "hit_queries": self._retrieval_hit_queries,
                    "hit_rate": retrieval_hit_rate,
                    "avg_hits_per_query": (
                        round(self._retrieval_hits_total / self._retrieval_queries, 4)
                        if self._retrieval_queries > 0
                        else None
                    ),
                    "avg_similarity": avg_similarity,
                },
                "write": {
                    "attempts": self._write_attempts,
                    "failures": self._write_failures,
                    "failure_rate": write_failure_rate,
                },
                "alerts": alerts,
                "thresholds": {
                    "retrieval_p95_ms": RETRIEVAL_P95_ALERT_THRESHOLD_MS,
                    "chat_p95_ms": CHAT_P95_ALERT_THRESHOLD_MS,
                    "write_failure_rate": WRITE_FAILURE_RATE_ALERT_THRESHOLD,
                    "retrieval_hit_rate": RETRIEVAL_HIT_RATE_ALERT_THRESHOLD,
                    "min_latency_samples_for_alert": MIN_SAMPLES_FOR_LATENCY_ALERT,
                    "min_write_samples_for_alert": MIN_SAMPLES_FOR_WRITE_ALERT,
                    "min_quality_samples_for_alert": MIN_SAMPLES_FOR_QUALITY_ALERT,
                },
            }
