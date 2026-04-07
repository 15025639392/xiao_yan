from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

from app.goals.models import Goal, GoalStatus
from app.memory.models import MemoryEvent
from app.utils.file_utils import read_json_file, write_json_file


class AdmissionDecision(str, Enum):
    ADMIT = "admit"
    DEFER = "defer"
    DROP = "drop"


class GoalCandidateSource(str, Enum):
    USER_TOPIC = "user_topic"
    WORLD_EVENT = "world_event"
    CHAIN_NEXT = "chain_next"


GoalAdmissionMode = Literal["off", "shadow", "enforce"]


class GoalCandidate(BaseModel):
    source_type: GoalCandidateSource
    title: str
    source_content: str | None = None
    chain_id: str | None = None
    parent_goal_id: str | None = None
    generation: int = 0
    retry_count: int = 0
    fingerprint: str | None = None


class DeferredGoalCandidate(BaseModel):
    candidate: GoalCandidate
    next_retry_at: datetime
    last_reason: str


class AdmissionResult(BaseModel):
    score: float
    recommended_decision: AdmissionDecision
    applied_decision: AdmissionDecision
    reason: str
    retry_at: datetime | None = None
    fingerprint: str


class GoalAdmissionStore:
    """Persistence layer for admission stats and deferred candidate queue."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path
        self._lock = Lock()
        self._state = {
            "deferred_candidates": [],
            "daily_stats": {},
            "seen_fingerprints": {},
        }
        self._load()

    @classmethod
    def in_memory(cls) -> "GoalAdmissionStore":
        return cls(storage_path=None)

    def _load(self) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        try:
            data = read_json_file(self.storage_path)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        self._state.update(
            {
                "deferred_candidates": data.get("deferred_candidates", []),
                "daily_stats": data.get("daily_stats", {}),
                "seen_fingerprints": data.get("seen_fingerprints", {}),
            }
        )

    def _persist(self) -> None:
        if self.storage_path is None:
            return
        write_json_file(
            self.storage_path,
            self._state,
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )

    def increment_stat(self, day: str, key: str) -> None:
        with self._lock:
            today_stats = self._state["daily_stats"].setdefault(day, {})
            today_stats[key] = int(today_stats.get(key, 0)) + 1
            self._persist()

    def get_stats(self, day: str) -> dict[str, int]:
        with self._lock:
            stats = self._state["daily_stats"].get(day, {})
            return {
                "admit": int(stats.get("admit", 0)),
                "defer": int(stats.get("defer", 0)),
                "drop": int(stats.get("drop", 0)),
                "wip_blocked": int(stats.get("wip_blocked", 0)),
            }

    def upsert_deferred_candidate(self, deferred: DeferredGoalCandidate) -> None:
        with self._lock:
            fingerprint = deferred.candidate.fingerprint
            if fingerprint is None:
                return
            payload = deferred.model_dump(mode="json")
            for index, existing in enumerate(self._state["deferred_candidates"]):
                existing_fp = existing.get("candidate", {}).get("fingerprint")
                if existing_fp == fingerprint:
                    # Keep the earlier retry timestamp to avoid extending delays.
                    existing_next_retry = existing.get("next_retry_at")
                    if isinstance(existing_next_retry, str):
                        existing_dt = datetime.fromisoformat(existing_next_retry)
                        incoming_dt = deferred.next_retry_at
                        if existing_dt <= incoming_dt:
                            payload["next_retry_at"] = existing_next_retry
                    self._state["deferred_candidates"][index] = payload
                    self._persist()
                    return
            self._state["deferred_candidates"].append(payload)
            self._persist()

    def remove_deferred_candidate(self, fingerprint: str | None) -> None:
        if not fingerprint:
            return
        with self._lock:
            self._state["deferred_candidates"] = [
                item
                for item in self._state["deferred_candidates"]
                if item.get("candidate", {}).get("fingerprint") != fingerprint
            ]
            self._persist()

    def pop_due_candidate(self, now: datetime) -> GoalCandidate | None:
        with self._lock:
            due_index = None
            due_time = None
            for index, item in enumerate(self._state["deferred_candidates"]):
                value = item.get("next_retry_at")
                if not isinstance(value, str):
                    continue
                try:
                    next_retry_at = datetime.fromisoformat(value)
                except ValueError:
                    continue
                if next_retry_at > now:
                    continue
                if due_time is None or next_retry_at < due_time:
                    due_time = next_retry_at
                    due_index = index

            if due_index is None:
                return None

            payload = self._state["deferred_candidates"].pop(due_index)
            self._persist()
            return GoalCandidate.model_validate(payload.get("candidate", {}))

    def set_seen(self, fingerprint: str, now: datetime, decision: AdmissionDecision) -> None:
        with self._lock:
            self._state["seen_fingerprints"][fingerprint] = {
                "decision": decision.value,
                "updated_at": now.isoformat(),
            }
            self._persist()

    def is_recently_seen(self, fingerprint: str, now: datetime, *, ttl: timedelta) -> bool:
        with self._lock:
            payload = self._state["seen_fingerprints"].get(fingerprint)
            if not isinstance(payload, dict):
                return False
            updated_at = payload.get("updated_at")
            if not isinstance(updated_at, str):
                return False
            try:
                updated_dt = datetime.fromisoformat(updated_at)
            except ValueError:
                return False
            return now - updated_dt <= ttl

    def deferred_queue_size(self) -> int:
        with self._lock:
            return len(self._state["deferred_candidates"])

    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy(self._state)


class GoalAdmissionService:
    COMMON_VERBS = (
        "整理",
        "推进",
        "检查",
        "确认",
        "查看",
        "回看",
        "分析",
        "规划",
        "准备",
        "执行",
        "验证",
        "优化",
        "总结",
        "学习",
        "修复",
        "重构",
        "实现",
        "测试",
    )
    GOAL_PREFIXES = (
        "持续理解用户最近在意的话题：",
        "继续消化自己刚经历的状态：",
        "继续推进：",
    )
    RETRY_BACKOFF_MINUTES = (5, 15, 30, 60)

    def __init__(
        self,
        store: GoalAdmissionStore,
        *,
        mode: GoalAdmissionMode = "shadow",
        min_score: float = 0.68,
        defer_score: float = 0.45,
        world_min_score: float = 0.75,
        world_defer_score: float = 0.52,
        chain_min_score: float = 0.62,
        chain_defer_score: float = 0.45,
        wip_limit: int = 2,
        world_enabled: bool = True,
        max_retries: int = 6,
    ) -> None:
        self.store = store
        self.mode: GoalAdmissionMode = mode
        self.min_score = min_score
        self.defer_score = defer_score
        self.world_min_score = world_min_score
        self.world_defer_score = world_defer_score
        self.chain_min_score = chain_min_score
        self.chain_defer_score = chain_defer_score
        self.wip_limit = wip_limit
        self.world_enabled = world_enabled
        self.max_retries = max_retries

    def canonical_topic(self, text: str) -> str:
        normalized = text.strip()
        normalized = normalized.replace("“", "").replace("”", "")
        changed = True
        while changed and normalized:
            changed = False
            for prefix in self.GOAL_PREFIXES:
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix):].strip()
                    changed = True
        normalized = re.sub(r"^[：:，,。.！!？?\s]+", "", normalized)
        normalized = re.sub(r"[：:，,。.！!？?\s]+$", "", normalized)
        return normalized[:48]

    def evaluate_candidate(
        self,
        candidate: GoalCandidate,
        *,
        now: datetime,
        active_goals: list[Goal],
        all_goals: list[Goal],
        recent_events: list[MemoryEvent],
    ) -> AdmissionResult:
        prepared = self._prepare_candidate(candidate)
        fingerprint = prepared.fingerprint or ""
        today = now.astimezone(timezone.utc).date().isoformat()

        if self.mode == "off":
            recommended = AdmissionDecision.ADMIT
            score = 1.0
            reason = "admission_disabled"
        else:
            score, recommended, reason = self._recommend(
                prepared,
                now=now,
                all_goals=all_goals,
                recent_events=recent_events,
            )
            if recommended == AdmissionDecision.ADMIT and len(active_goals) >= self.wip_limit:
                recommended = AdmissionDecision.DEFER
                reason = "wip_full"
                self.store.increment_stat(today, "wip_blocked")

        self.store.increment_stat(today, recommended.value)

        applied = recommended if self.mode == "enforce" else AdmissionDecision.ADMIT
        retry_at: datetime | None = None

        if self.mode == "enforce":
            if applied == AdmissionDecision.DEFER:
                retry_at = self._enqueue_or_update_deferred(prepared, now=now, reason=reason)
            else:
                self.store.remove_deferred_candidate(fingerprint)
                self.store.set_seen(fingerprint, now, applied)
        elif recommended in {AdmissionDecision.DEFER, AdmissionDecision.DROP}:
            self.store.set_seen(fingerprint, now, recommended)

        return AdmissionResult(
            score=round(score, 4),
            recommended_decision=recommended,
            applied_decision=applied,
            reason=reason,
            retry_at=retry_at,
            fingerprint=fingerprint,
        )

    def pop_due_candidate(self, now: datetime) -> GoalCandidate | None:
        return self.store.pop_due_candidate(now)

    def get_stats(self, now: datetime | None = None) -> dict:
        moment = now or datetime.now(timezone.utc)
        day = moment.astimezone(timezone.utc).date().isoformat()
        return {
            "mode": self.mode,
            "today": self.store.get_stats(day),
            "deferred_queue_size": self.store.deferred_queue_size(),
            "wip_limit": self.wip_limit,
            "thresholds": {
                "user_topic": {"min_score": self.min_score, "defer_score": self.defer_score},
                "world_event": {"min_score": self.world_min_score, "defer_score": self.world_defer_score},
                "chain_next": {"min_score": self.chain_min_score, "defer_score": self.chain_defer_score},
            },
        }

    def _prepare_candidate(self, candidate: GoalCandidate) -> GoalCandidate:
        if candidate.fingerprint is not None:
            return candidate
        canonical = self.canonical_topic(candidate.source_content or candidate.title)
        digest = hashlib.sha1(
            f"{candidate.source_type.value}|{canonical}|{candidate.chain_id or ''}|{candidate.parent_goal_id or ''}|{candidate.generation}".encode(
                "utf-8"
            )
        ).hexdigest()[:24]
        return candidate.model_copy(update={"fingerprint": digest})

    def _recommend(
        self,
        candidate: GoalCandidate,
        *,
        now: datetime,
        all_goals: list[Goal],
        recent_events: list[MemoryEvent],
    ) -> tuple[float, AdmissionDecision, str]:
        fingerprint = candidate.fingerprint or ""
        if candidate.source_type in {GoalCandidateSource.USER_TOPIC, GoalCandidateSource.WORLD_EVENT}:
            if self.store.is_recently_seen(fingerprint, now, ttl=timedelta(minutes=5)):
                return 0.0, AdmissionDecision.DEFER, "duplicate_candidate"

        if candidate.source_type == GoalCandidateSource.WORLD_EVENT and not self.world_enabled:
            return 0.0, AdmissionDecision.DEFER, "world_event_disabled"

        if candidate.source_type == GoalCandidateSource.CHAIN_NEXT:
            score = self._score_chain_candidate(candidate)
            return score, self._decision_from_threshold(score, self.chain_min_score, self.chain_defer_score), "chain_score"

        score = self._score_user_world_candidate(candidate, all_goals=all_goals, recent_events=recent_events)
        if candidate.source_type == GoalCandidateSource.WORLD_EVENT:
            decision = self._decision_from_threshold(score, self.world_min_score, self.world_defer_score)
            return score, decision, "world_score"
        return score, self._decision_from_threshold(score, self.min_score, self.defer_score), "user_score"

    def _score_user_world_candidate(
        self,
        candidate: GoalCandidate,
        *,
        all_goals: list[Goal],
        recent_events: list[MemoryEvent],
    ) -> float:
        actionability = self._actionability_score(candidate.title)
        persistence = self._persistence_score(candidate, recent_events=recent_events)
        novelty = self._novelty_score(candidate, all_goals=all_goals)
        return max(0.0, min(1.0, 0.5 * actionability + 0.3 * persistence + 0.2 * novelty))

    def _score_chain_candidate(self, candidate: GoalCandidate) -> float:
        actionability = self._actionability_score(candidate.title)
        generation = max(candidate.generation, 0)
        if generation <= 2:
            momentum = 1.0
        elif generation <= 4:
            momentum = 0.75
        elif generation <= 8:
            momentum = 0.45
        else:
            momentum = 0.15
        return max(0.0, min(1.0, 0.7 * actionability + 0.3 * momentum))

    def _actionability_score(self, title: str) -> float:
        if self._action_command_for_goal(title) is not None:
            return 1.0
        if any(verb in title for verb in self.COMMON_VERBS):
            return 0.6
        return 0.2

    def _action_command_for_goal(self, goal_title: str) -> str | None:
        if "时间" in goal_title or "几点" in goal_title:
            return "date +%H:%M"
        if "目录" in goal_title or "文件" in goal_title:
            return "pwd"
        return None

    def _persistence_score(self, candidate: GoalCandidate, *, recent_events: list[MemoryEvent]) -> float:
        topic = self.canonical_topic(candidate.source_content or candidate.title)
        if not topic:
            return 0.0
        hits = 0
        for event in recent_events:
            if self._topic_match(topic, event.content):
                hits += 1
        if hits >= 2:
            return 1.0
        if hits == 1:
            return 0.5
        return 0.0

    def _novelty_score(self, candidate: GoalCandidate, *, all_goals: list[Goal]) -> float:
        topic = self.canonical_topic(candidate.source_content or candidate.title)
        if not topic:
            return 0.0
        compared = [
            self.canonical_topic(goal.title)
            for goal in all_goals
            if goal.status in {GoalStatus.ACTIVE, GoalStatus.PAUSED}
        ]
        compared = [item for item in compared if item]
        if not compared:
            return 1.0
        max_similarity = max(SequenceMatcher(a=topic, b=item).ratio() for item in compared)
        return max(0.0, 1.0 - max_similarity)

    def _topic_match(self, topic: str, content: str) -> bool:
        if topic in content:
            return True
        keywords = [item for item in re.split(r"[和与及、，,。.!！？?：:\s]+", topic) if len(item) >= 2]
        return any(keyword in content for keyword in keywords)

    def _decision_from_threshold(
        self,
        score: float,
        min_score: float,
        defer_score: float,
    ) -> AdmissionDecision:
        if score >= min_score:
            return AdmissionDecision.ADMIT
        if score >= defer_score:
            return AdmissionDecision.DEFER
        return AdmissionDecision.DROP

    def _enqueue_or_update_deferred(
        self,
        candidate: GoalCandidate,
        *,
        now: datetime,
        reason: str,
    ) -> datetime | None:
        fingerprint = candidate.fingerprint
        if fingerprint is None:
            return None

        retry_count = max(candidate.retry_count, 0)
        if retry_count >= self.max_retries:
            self.store.remove_deferred_candidate(fingerprint)
            self.store.set_seen(fingerprint, now, AdmissionDecision.DROP)
            return None

        next_retry_at = now + timedelta(minutes=self._retry_backoff_minutes(retry_count))
        deferred = DeferredGoalCandidate(
            candidate=candidate.model_copy(update={"retry_count": retry_count + 1}),
            next_retry_at=next_retry_at,
            last_reason=reason,
        )
        self.store.upsert_deferred_candidate(deferred)
        self.store.set_seen(fingerprint, now, AdmissionDecision.DEFER)
        return next_retry_at

    def _retry_backoff_minutes(self, retry_count: int) -> int:
        index = min(max(retry_count, 0), len(self.RETRY_BACKOFF_MINUTES) - 1)
        return self.RETRY_BACKOFF_MINUTES[index]
