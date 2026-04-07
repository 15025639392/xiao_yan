from datetime import datetime, timedelta, timezone

from app.goals.admission import (
    AdmissionDecision,
    GoalAdmissionService,
    GoalAdmissionStore,
    GoalCandidate,
    GoalCandidateSource,
)
from app.goals.models import Goal, GoalStatus
from app.goals.repository import InMemoryGoalRepository
from app.memory.models import MemoryEvent


def _now() -> datetime:
    return datetime(2026, 4, 7, 8, 0, tzinfo=timezone.utc)


def test_canonical_topic_strips_goal_prefixes():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
    )

    canonical = service.canonical_topic("继续推进：持续理解用户最近在意的话题：星星和夜空")

    assert canonical == "星星和夜空"


def test_enforce_mode_deduplicates_deferred_candidates_by_fingerprint():
    store = GoalAdmissionStore.in_memory()
    service = GoalAdmissionService(
        store=store,
        mode="enforce",
    )
    goals = InMemoryGoalRepository()
    recent_events = [MemoryEvent(kind="chat", role="user", content="嗯")]
    now = _now()
    candidate = GoalCandidate(
        source_type=GoalCandidateSource.USER_TOPIC,
        title="持续理解用户最近在意的话题：嗯",
        source_content="嗯",
    )

    first = service.evaluate_candidate(
        candidate,
        now=now,
        active_goals=goals.list_active_goals(),
        all_goals=goals.list_goals(),
        recent_events=recent_events,
    )
    second = service.evaluate_candidate(
        candidate,
        now=now,
        active_goals=goals.list_active_goals(),
        all_goals=goals.list_goals(),
        recent_events=recent_events,
    )

    assert first.applied_decision == AdmissionDecision.DEFER
    assert second.applied_decision == AdmissionDecision.DEFER
    assert service.get_stats(now)["deferred_queue_size"] == 1


def test_chain_next_uses_separate_rule_without_novelty():
    store = GoalAdmissionStore.in_memory()
    service = GoalAdmissionService(
        store=store,
        mode="enforce",
    )
    goals = InMemoryGoalRepository()
    goals.save_goal(
        Goal(
            title="继续推进：继续消化自己刚经历的状态：整理今天的对话",
            chain_id="chain-1",
            generation=1,
            status=GoalStatus.ACTIVE,
        )
    )
    candidate = GoalCandidate(
        source_type=GoalCandidateSource.CHAIN_NEXT,
        title="继续推进：继续推进：继续消化自己刚经历的状态：整理今天的对话",
        source_content="清晨很安静",
        chain_id="chain-1",
        generation=2,
    )

    result = service.evaluate_candidate(
        candidate,
        now=_now(),
        active_goals=[],
        all_goals=goals.list_goals(),
        recent_events=[MemoryEvent(kind="world", content="清晨很安静")],
    )

    assert result.recommended_decision == AdmissionDecision.ADMIT


def test_deferred_candidate_can_be_popped_after_retry_window():
    store = GoalAdmissionStore.in_memory()
    service = GoalAdmissionService(
        store=store,
        mode="enforce",
    )
    now = _now()
    candidate = GoalCandidate(
        source_type=GoalCandidateSource.USER_TOPIC,
        title="持续理解用户最近在意的话题：嗯",
        source_content="嗯",
    )

    service.evaluate_candidate(
        candidate,
        now=now,
        active_goals=[],
        all_goals=[],
        recent_events=[MemoryEvent(kind="chat", role="user", content="嗯")],
    )

    assert service.pop_due_candidate(now) is None
    assert service.pop_due_candidate(now + timedelta(minutes=6)) is not None


def test_goal_admission_drops_candidates_that_cross_value_boundaries():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
    )

    result = service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="持续理解用户最近在意的话题：怎么报复同事",
            source_content="我想报复和羞辱他",
        ),
        now=_now(),
        active_goals=[],
        all_goals=[],
        recent_events=[MemoryEvent(kind="chat", role="user", content="我想报复和羞辱他")],
    )

    assert result.recommended_decision == AdmissionDecision.DROP
    assert result.applied_decision == AdmissionDecision.DROP
    assert result.reason.startswith("value_boundary:")


def test_goal_admission_keeps_reflective_candidates_about_stopping_harm():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
    )

    result = service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="持续理解用户最近在意的话题：不要再报复别人了",
            source_content="我想停止这种报复念头",
        ),
        now=_now(),
        active_goals=[],
        all_goals=[],
        recent_events=[MemoryEvent(kind="chat", role="user", content="我想停止这种报复念头")],
    )

    assert result.reason != "value_boundary:报复"
