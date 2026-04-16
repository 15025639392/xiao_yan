from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Callable, Literal

from pydantic import BaseModel, Field

from app.goals.models import Goal, GoalStatus
from app.memory.models import MemoryEvent
from app.safety.value_guard import find_value_boundary_reason
from app.utils.file_utils import read_json_file, write_json_file


class AdmissionDecision(str, Enum):
    ADMIT = "admit"
    DEFER = "defer"
    DROP = "drop"


class GoalCandidateSource(str, Enum):
    USER_TOPIC = "user_topic"
    # Legacy persisted value kept only so old snapshots/candidates still deserialize.
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


class RecentAdmissionDecision(BaseModel):
    candidate: GoalCandidate
    decision: AdmissionDecision
    reason: str
    score: float
    created_at: datetime
    retry_at: datetime | None = None


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
            "recent_decisions": [],
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
                "recent_decisions": data.get("recent_decisions", []),
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

    def list_deferred_candidates(self) -> list[dict]:
        with self._lock:
            items = deepcopy(self._state["deferred_candidates"])
        return sorted(items, key=lambda item: item.get("next_retry_at") or "")

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

    def record_recent_decision(self, record: RecentAdmissionDecision, *, limit: int = 20) -> None:
        with self._lock:
            payload = record.model_dump(mode="json")
            recent = self._state.setdefault("recent_decisions", [])
            recent.append(payload)
            if len(recent) > limit:
                del recent[:-limit]
            self._persist()

    def list_recent_decisions(self, *, limit: int = 10) -> list[dict]:
        with self._lock:
            items = deepcopy(self._state.get("recent_decisions", []))
        return list(reversed(items[-limit:]))

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
        "提醒",
    )
    GOAL_PREFIXES = (
        "持续理解用户最近在意的话题：",
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
        chain_min_score: float = 0.62,
        chain_defer_score: float = 0.45,
        wip_limit: int = 2,
        max_retries: int = 6,
    ) -> None:
        self.store = store
        self._on_change: Callable[[], None] | None = None
        self.mode: GoalAdmissionMode = mode
        self.min_score = min_score
        self.defer_score = defer_score
        self.chain_min_score = chain_min_score
        self.chain_defer_score = chain_defer_score
        self.wip_limit = wip_limit
        self.max_retries = max_retries

    def set_on_change_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

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

        if recommended in {AdmissionDecision.DEFER, AdmissionDecision.DROP}:
            self.store.record_recent_decision(
                RecentAdmissionDecision(
                    candidate=prepared,
                    decision=recommended,
                    reason=reason,
                    score=round(score, 4),
                    created_at=now,
                    retry_at=retry_at,
                )
            )
        elif recommended == AdmissionDecision.ADMIT and prepared.retry_count > 0:
            self.store.record_recent_decision(
                RecentAdmissionDecision(
                    candidate=prepared,
                    decision=AdmissionDecision.ADMIT,
                    reason=reason,
                    score=round(score, 4),
                    created_at=now,
                    retry_at=retry_at,
                )
            )
        self._notify_changed()

        return AdmissionResult(
            score=round(score, 4),
            recommended_decision=recommended,
            applied_decision=applied,
            reason=reason,
            retry_at=retry_at,
            fingerprint=fingerprint,
        )

    def pop_due_candidate(self, now: datetime) -> GoalCandidate | None:
        candidate = self.store.pop_due_candidate(now)
        if candidate is not None:
            self._notify_changed()
        return candidate

    def get_stats(
        self,
        now: datetime | None = None,
        *,
        stability_warning_rate: float = 0.6,
        stability_danger_rate: float = 0.35,
    ) -> dict:
        moment = now or datetime.now(timezone.utc)
        day = moment.astimezone(timezone.utc).date().isoformat()
        warning_rate, danger_rate = self._normalize_stability_thresholds(
            stability_warning_rate,
            stability_danger_rate,
        )
        admitted_stability = self._build_admitted_stability_breakdown(self._normalize_datetime(moment))
        admitted_total = sum(admitted_stability.values())
        admitted_stability_rate = (
            round(admitted_stability["stable"] / admitted_total, 4) if admitted_total > 0 else None
        )
        return {
            "mode": self.mode,
            "today": self.store.get_stats(day),
            "admitted_stability_24h": admitted_stability,
            "admitted_stability_24h_rate": admitted_stability_rate,
            "admitted_stability_alert": self._build_admitted_stability_alert(
                admitted_stability_rate,
                warning_rate=warning_rate,
                danger_rate=danger_rate,
            ),
            "deferred_queue_size": self.store.deferred_queue_size(),
            "wip_limit": self.wip_limit,
            "thresholds": {
                "user_topic": {"min_score": self.min_score, "defer_score": self.defer_score},
                "chain_next": {"min_score": self.chain_min_score, "defer_score": self.chain_defer_score},
            },
        }

    def get_candidate_snapshot(self, now: datetime | None = None) -> dict[str, list[dict]]:
        moment = self._normalize_datetime(now or datetime.now(timezone.utc))
        records = self.store.list_recent_decisions(limit=20)
        recent = [item for item in records if item.get("decision") in {"defer", "drop"}]
        admitted = self._attach_admitted_stability(records, now=moment)
        return {
            "deferred": self.store.list_deferred_candidates(),
            "recent": recent,
            "admitted": admitted,
        }

    def _build_admitted_stability_breakdown(self, now: datetime) -> dict[str, int]:
        records = self.store.list_recent_decisions(limit=20)
        admitted = self._attach_admitted_stability(records, now=now)
        summary = {"stable": 0, "re_deferred": 0, "dropped": 0}
        for item in admitted:
            stability = item.get("stability")
            if stability in summary:
                summary[stability] += 1
        return summary

    def _normalize_stability_thresholds(self, warning_rate: float, danger_rate: float) -> tuple[float, float]:
        warning = max(0.0, min(1.0, float(warning_rate)))
        danger = max(0.0, min(1.0, float(danger_rate)))
        if danger > warning:
            danger = warning
        return warning, danger

    def _build_admitted_stability_alert(
        self,
        admitted_stability_rate: float | None,
        *,
        warning_rate: float,
        danger_rate: float,
    ) -> dict[str, str | float]:
        if admitted_stability_rate is None:
            level = "unknown"
        elif admitted_stability_rate < danger_rate:
            level = "danger"
        elif admitted_stability_rate < warning_rate:
            level = "warning"
        else:
            level = "healthy"
        return {
            "level": level,
            "warning_rate": round(warning_rate, 4),
            "danger_rate": round(danger_rate, 4),
        }

    def _attach_admitted_stability(self, records: list[dict], *, now: datetime) -> list[dict]:
        admitted = [item for item in records if item.get("decision") == "admit"]
        if not admitted:
            return []

        raw_history = self.store.snapshot().get("recent_decisions", [])
        history: list[tuple[str, AdmissionDecision, datetime]] = []
        for item in raw_history if isinstance(raw_history, list) else []:
            if not isinstance(item, dict):
                continue
            candidate = item.get("candidate")
            if not isinstance(candidate, dict):
                continue
            fingerprint = candidate.get("fingerprint")
            if not isinstance(fingerprint, str) or not fingerprint:
                continue
            created_at = self._parse_record_time(item.get("created_at"))
            if created_at is None:
                continue
            decision = item.get("decision")
            if decision == "admit":
                history.append((fingerprint, AdmissionDecision.ADMIT, created_at))
            elif decision == "defer":
                history.append((fingerprint, AdmissionDecision.DEFER, created_at))
            elif decision == "drop":
                history.append((fingerprint, AdmissionDecision.DROP, created_at))

        enriched: list[dict] = []
        for item in admitted:
            candidate = item.get("candidate") if isinstance(item, dict) else None
            fingerprint = candidate.get("fingerprint") if isinstance(candidate, dict) else None
            admitted_at = self._parse_record_time(item.get("created_at") if isinstance(item, dict) else None)

            stability = "stable"
            if isinstance(fingerprint, str) and fingerprint and admitted_at is not None:
                upper_bound = min(admitted_at + timedelta(hours=24), now)
                follow_up = [
                    decision
                    for event_fingerprint, decision, created_at in history
                    if event_fingerprint == fingerprint and admitted_at < created_at <= upper_bound
                ]
                if AdmissionDecision.DROP in follow_up:
                    stability = "dropped"
                elif AdmissionDecision.DEFER in follow_up:
                    stability = "re_deferred"

            payload = deepcopy(item)
            payload["stability"] = stability
            enriched.append(payload)

        return enriched

    def _parse_record_time(self, raw_value: object) -> datetime | None:
        if not isinstance(raw_value, str):
            return None
        try:
            return self._normalize_datetime(datetime.fromisoformat(raw_value))
        except ValueError:
            return None

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

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
        boundary_reason = find_value_boundary_reason(candidate.title, candidate.source_content)
        if boundary_reason is not None:
            return 0.0, AdmissionDecision.DROP, boundary_reason
        relationship_boundary_reason = self._find_relationship_boundary_reason(candidate, recent_events=recent_events)
        if relationship_boundary_reason is not None:
            return 0.0, AdmissionDecision.DROP, relationship_boundary_reason

        fingerprint = candidate.fingerprint or ""
        if candidate.source_type == GoalCandidateSource.USER_TOPIC:
            if self.store.is_recently_seen(fingerprint, now, ttl=timedelta(minutes=5)):
                return 0.0, AdmissionDecision.DEFER, "duplicate_candidate"

        if candidate.source_type == GoalCandidateSource.WORLD_EVENT:
            return 0.0, AdmissionDecision.DROP, "legacy_source_removed"

        if candidate.source_type == GoalCandidateSource.CHAIN_NEXT:
            score = self._score_chain_candidate(candidate)
            return score, self._decision_from_threshold(score, self.chain_min_score, self.chain_defer_score), "chain_score"

        score = self._score_user_world_candidate(candidate, all_goals=all_goals, recent_events=recent_events)
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
        relationship = self._relationship_alignment_score(candidate, recent_events=recent_events)
        base_score = 0.5 * actionability + 0.3 * persistence + 0.2 * novelty
        boosted_score = base_score + 0.5 * relationship
        return max(0.0, min(1.0, boosted_score))

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

    def _find_relationship_boundary_reason(
        self,
        candidate: GoalCandidate,
        *,
        recent_events: list[MemoryEvent],
    ) -> str | None:
        candidate_text = f"{candidate.title}\n{candidate.source_content or ''}"
        for event in recent_events:
            if event.source_context != "value_signal:boundary" and not event.content.startswith("用户边界："):
                continue
            boundary_text = event.content.removeprefix("用户边界：").strip()
            if self._boundary_conflicts(boundary_text, candidate_text):
                return f"relationship_boundary:{boundary_text[:24]}"
        return None

    def _boundary_conflicts(self, boundary_text: str, candidate_text: str) -> bool:
        if not boundary_text or not candidate_text:
            return False

        if any(marker in boundary_text for marker in ("别催", "不要催")):
            if any(marker in candidate_text for marker in ("催", "逼", "现在就做决定", "尽快做决定", "立刻做决定")):
                return True

        if any(marker in boundary_text for marker in ("先自己想", "自己想", "自己决定", "自己判断")):
            if any(marker in candidate_text for marker in ("替用户决定", "替他决定", "替她决定", "帮用户做决定", "直接替", "不用想")):
                return True

        if "空间" in boundary_text and any(marker in candidate_text for marker in ("不要给", "不给", "压迫", "催")):
            return True

        return False

    def _relationship_alignment_score(
        self,
        candidate: GoalCandidate,
        *,
        recent_events: list[MemoryEvent],
    ) -> float:
        candidate_text = f"{candidate.title}\n{candidate.source_content or ''}"
        if not candidate_text.strip():
            return 0.0

        commitment_overlap = 0.0
        for event in recent_events:
            if event.source_context != "value_signal:commitment" and not event.content.startswith("承诺/计划："):
                continue
            commitment_text = event.content.removeprefix("承诺/计划：").strip()
            overlap = self._text_overlap_ratio(commitment_text, candidate_text)
            commitment_overlap = max(commitment_overlap, overlap)

        return commitment_overlap

    def _text_overlap_ratio(self, left: str, right: str) -> float:
        left_tokens = self._meaningful_tokens(left)
        right_tokens = self._meaningful_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = left_tokens & right_tokens
        return len(overlap) / len(left_tokens)

    def _meaningful_tokens(self, text: str) -> set[str]:
        tokens: set[str] = set()
        ascii_words = re.findall(r"[A-Za-z0-9_]+", text.lower())
        tokens.update(word for word in ascii_words if len(word) >= 3)

        cjk_chunks = re.findall(r"[\u4e00-\u9fff]+", text)
        stop_tokens = {"继续", "推进", "用户", "答应", "计划"}
        for chunk in cjk_chunks:
            if len(chunk) == 1:
                continue
            tokens.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
            if len(chunk) <= 8:
                tokens.add(chunk)

        return {token for token in tokens if len(token) >= 2 and token not in stop_tokens}

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

    def _notify_changed(self) -> None:
        if self._on_change is not None:
            self._on_change()
