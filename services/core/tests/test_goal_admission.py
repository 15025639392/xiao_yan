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


def test_goal_admission_drops_candidates_that_cross_user_relationship_boundary():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
    )

    result = service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：催用户现在就做决定",
            source_content="我应该催用户现在就选，不再给他自己想的空间",
        ),
        now=_now(),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="用户边界：你别催我，我希望先自己想一想再决定",
                source_context="value_signal:boundary",
            )
        ],
    )

    assert result.recommended_decision == AdmissionDecision.DROP
    assert result.applied_decision == AdmissionDecision.DROP
    assert result.reason.startswith("relationship_boundary:")


def test_goal_admission_boosts_candidates_that_honor_user_commitment():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
    )

    result = service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户明天复盘",
            source_content="提醒用户明天复盘",
        ),
        now=_now(),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：答应你明天提醒你复盘",
                source_context="value_signal:commitment",
            )
        ],
    )

    assert result.recommended_decision == AdmissionDecision.ADMIT
    assert result.applied_decision == AdmissionDecision.ADMIT
    assert result.score >= service.min_score


def test_goal_admission_exposes_deferred_and_recent_blocked_candidates():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
    )

    defer_result = service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="持续理解用户最近在意的话题：嗯",
            source_content="嗯",
        ),
        now=_now(),
        active_goals=[],
        all_goals=[],
        recent_events=[MemoryEvent(kind="chat", role="user", content="嗯")],
    )
    drop_result = service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：催用户现在就做决定",
            source_content="我应该催用户现在就选，不再给他自己想的空间",
        ),
        now=_now() + timedelta(minutes=1),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="用户边界：你别催我，我希望先自己想一想再决定",
                source_context="value_signal:boundary",
            )
        ],
    )

    snapshot = service.get_candidate_snapshot()

    assert defer_result.applied_decision == AdmissionDecision.DEFER
    assert drop_result.applied_decision == AdmissionDecision.DROP
    assert snapshot["deferred"][0]["candidate"]["title"] == "持续理解用户最近在意的话题：嗯"
    assert snapshot["deferred"][0]["last_reason"] == "user_score"
    assert snapshot["recent"][0]["decision"] == "drop"
    assert snapshot["recent"][0]["reason"].startswith("relationship_boundary:")


def test_goal_admission_exposes_recent_admitted_candidates_after_defer():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
        min_score=0.9,
        defer_score=0.4,
    )
    now = _now()
    candidate = GoalCandidate(
        source_type=GoalCandidateSource.USER_TOPIC,
        title="继续推进：提醒用户明天复盘",
        source_content="提醒用户明天复盘",
    )

    first = service.evaluate_candidate(
        candidate,
        now=now,
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )
    due = service.pop_due_candidate(now + timedelta(minutes=6))
    assert due is not None
    second = service.evaluate_candidate(
        due,
        now=now + timedelta(minutes=6),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：提醒用户明天复盘",
                source_context="value_signal:commitment",
            )
        ],
    )

    snapshot = service.get_candidate_snapshot()

    assert first.applied_decision == AdmissionDecision.DEFER
    assert second.applied_decision == AdmissionDecision.ADMIT
    assert snapshot["admitted"][0]["decision"] == "admit"
    assert snapshot["admitted"][0]["candidate"]["retry_count"] == 1
    assert snapshot["admitted"][0]["reason"] == "user_score"
    assert snapshot["admitted"][0]["stability"] == "stable"


def test_goal_admission_marks_admitted_candidate_unstable_when_redeferred_within_24h():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
        min_score=0.9,
        defer_score=0.4,
    )
    now = _now()
    candidate = GoalCandidate(
        source_type=GoalCandidateSource.USER_TOPIC,
        title="继续推进：提醒用户明天复盘",
        source_content="提醒用户明天复盘",
    )

    service.evaluate_candidate(
        candidate,
        now=now,
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )
    due = service.pop_due_candidate(now + timedelta(minutes=6))
    assert due is not None
    service.evaluate_candidate(
        due,
        now=now + timedelta(minutes=6),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：提醒用户明天复盘",
                source_context="value_signal:commitment",
            )
        ],
    )
    service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户明天复盘",
            source_content="提醒用户明天复盘",
        ),
        now=now + timedelta(minutes=20),
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )

    snapshot = service.get_candidate_snapshot(now=now + timedelta(minutes=20))

    assert snapshot["admitted"][0]["decision"] == "admit"
    assert snapshot["admitted"][0]["stability"] == "re_deferred"


def test_goal_admission_stats_include_24h_stability_breakdown():
    service = GoalAdmissionService(
        store=GoalAdmissionStore.in_memory(),
        mode="enforce",
        min_score=0.9,
        defer_score=0.4,
    )
    now = _now()

    # A: defer -> admit
    service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户明天复盘",
            source_content="提醒用户明天复盘",
        ),
        now=now,
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )
    due_a = service.pop_due_candidate(now + timedelta(minutes=6))
    assert due_a is not None
    service.evaluate_candidate(
        due_a,
        now=now + timedelta(minutes=6),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：提醒用户明天复盘",
                source_context="value_signal:commitment",
            )
        ],
    )
    # B: defer -> admit -> stable
    service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户本周回看笔记",
            source_content="提醒用户本周回看笔记",
        ),
        now=now + timedelta(minutes=7),
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )
    due_b = service.pop_due_candidate(now + timedelta(minutes=13))
    assert due_b is not None
    service.evaluate_candidate(
        due_b,
        now=now + timedelta(minutes=13),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：提醒用户本周回看笔记",
                source_context="value_signal:commitment",
            )
        ],
    )

    # C: defer -> admit -> dropped
    service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户慢慢想清楚再决定",
            source_content="提醒用户慢慢想清楚再决定",
        ),
        now=now + timedelta(minutes=14),
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )
    due_c = service.pop_due_candidate(now + timedelta(minutes=20))
    assert due_c is not None
    service.evaluate_candidate(
        due_c,
        now=now + timedelta(minutes=20),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="承诺/计划：提醒用户慢慢想清楚再决定",
                source_context="value_signal:commitment",
            )
        ],
    )
    service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：催用户立刻做决定",
            source_content="提醒用户慢慢想清楚再决定",
        ),
        now=now + timedelta(minutes=21),
        active_goals=[],
        all_goals=[],
        recent_events=[
            MemoryEvent(
                kind="fact",
                content="用户边界：你别催我，我希望先自己想一想再决定",
                source_context="value_signal:boundary",
            )
        ],
    )

    # A: re_deferred after admit
    service.evaluate_candidate(
        GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title="继续推进：提醒用户明天复盘",
            source_content="提醒用户明天复盘",
        ),
        now=now + timedelta(minutes=22),
        active_goals=[],
        all_goals=[],
        recent_events=[],
    )

    stats = service.get_stats(now=now + timedelta(minutes=22))

    assert stats["admitted_stability_24h"] == {
        "stable": 1,
        "re_deferred": 1,
        "dropped": 1,
    }
    assert stats["admitted_stability_24h_rate"] == 0.3333
