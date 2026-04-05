from datetime import datetime, timedelta, timezone

from app.agent.loop import AutonomyLoop
from app.domain.models import BeingState, FocusMode, SelfImprovementStatus, WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import InMemoryGoalRepository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


class StubCommandRunner:
    def __init__(self, outputs: dict[str, str]) -> None:
        self.outputs = outputs
        self.commands: list[str] = []

    def run(self, command: str):
        self.commands.append(command)
        return type(
            "CommandResult",
            (),
            {
                "command": command,
                "output": self.outputs[command],
            },
        )()


def test_tick_once_keeps_sleeping_state_unchanged():
    store = StateStore()
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo)

    state = loop.tick_once()

    assert state.mode == WakeMode.SLEEPING
    assert state.current_thought is None


def test_tick_once_updates_awake_state_with_proactive_thought():
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你喜欢星星吗"))
    loop = AutonomyLoop(store, repo)

    state = loop.tick_once()

    assert state.mode == WakeMode.AWAKE
    assert state.current_thought is not None
    assert "星星" in state.current_thought


def test_tick_once_adds_one_proactive_assistant_message_for_latest_user_message():
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你还记得星星吗"))
    loop = AutonomyLoop(store, repo)

    first_state = loop.tick_once()
    recent_after_first_tick = list(reversed(repo.list_recent(limit=5)))

    second_state = loop.tick_once()
    recent_after_second_tick = list(reversed(repo.list_recent(limit=5)))

    assert first_state.last_proactive_source == "你还记得星星吗"
    assert second_state.last_proactive_source == "你还记得星星吗"
    assert [event.role for event in recent_after_first_tick] == ["user", "assistant"]
    assert [event.role for event in recent_after_second_tick] == ["user", "assistant"]
    assert "星星" in recent_after_first_tick[-1].content


def test_tick_once_respects_proactive_cooldown():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            last_proactive_source="之前的话题",
            last_proactive_at=now - timedelta(seconds=20),
        )
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你现在在想什么"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()
    recent = list(reversed(repo.list_recent(limit=5)))

    assert state.current_thought is None
    assert [event.role for event in recent] == ["user"]


def test_tick_once_generates_time_aware_proactive_message():
    now = datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你喜欢夜空吗"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "晚上" in state.current_thought


def test_tick_once_surfaces_pending_goal_as_current_focus():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(mode=WakeMode.AWAKE, active_goal_ids=["整理今天的对话记忆"])
    )
    repo = InMemoryMemoryRepository()
    goals = InMemoryGoalRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "整理今天的对话记忆" in state.current_thought


def test_tick_once_generates_goal_from_latest_user_topic_when_no_active_goals():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="最近总在想星星和夜空"))
    goals = InMemoryGoalRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()
    active_goals = goals.list_active_goals()

    assert len(active_goals) == 1
    assert "星星和夜空" in active_goals[0].title
    assert state.active_goal_ids == [active_goals[0].id]
    assert "星星和夜空" in state.current_thought


def test_tick_once_clears_paused_goal_from_focus_without_continuing_it():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="整理今天的对话记忆",
            source="你还记得星星吗",
            status=GoalStatus.PAUSED,
        )
    )
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            active_goal_ids=[goal.id],
            last_proactive_source="你还记得星星吗",
            last_proactive_at=now - timedelta(seconds=20),
        )
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你还记得星星吗"))
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.active_goal_ids == []
    assert state.current_thought is None


def test_tick_once_emits_completion_thought_once_for_completed_goal():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    later = now + timedelta(seconds=61)
    times = iter([now, later])
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="整理今天的对话记忆",
            source="最近总在想星星和夜空",
            status=GoalStatus.COMPLETED,
        )
    )
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            active_goal_ids=[goal.id],
            last_proactive_source="最近总在想星星和夜空",
        )
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="最近总在想星星和夜空"))
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: next(times))

    first_state = loop.tick_once()
    second_state = loop.tick_once()

    assert first_state.active_goal_ids == []
    assert first_state.current_thought is not None
    assert "整理今天的对话记忆" in first_state.current_thought
    assert second_state.active_goal_ids == []
    assert second_state.current_thought is not None
    assert "整理今天的对话记忆" not in second_state.current_thought
    assert goals.list_active_goals() == []


def test_tick_once_clears_abandoned_goal_without_completion_thought():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="继续理解用户关于夜空的话题",
            source="你喜欢夜空吗",
            status=GoalStatus.ABANDONED,
        )
    )
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            active_goal_ids=[goal.id],
            last_proactive_at=now - timedelta(seconds=20),
        )
    )
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.active_goal_ids == []
    assert state.current_thought is None


def test_tick_once_goal_focus_reflects_low_energy_world_state():
    now = datetime(2026, 4, 4, 23, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(mode=WakeMode.AWAKE, active_goal_ids=["整理今天的对话记忆"])
    )
    repo = InMemoryMemoryRepository()
    goals = InMemoryGoalRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "有点困" in state.current_thought
    assert "整理今天的对话记忆" in state.current_thought


def test_tick_once_goal_focus_mentions_chain_progress():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    root = goals.save_goal(
        Goal(
            title="继续消化自己刚经历的状态：整理今天的对话",
            source="清晨很安静，我还惦记着“整理今天的对话记忆”。",
            status=GoalStatus.COMPLETED,
            chain_id="chain-1",
            generation=0,
        )
    )
    child = goals.save_goal(
        Goal(
            title="继续推进：继续消化自己刚经历的状态：整理今天的对话",
            source=root.source,
            status=GoalStatus.ACTIVE,
            chain_id="chain-1",
            parent_goal_id=root.id,
            generation=1,
        )
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[child.id]))
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "第2步" in state.current_thought
    assert "继续推进" in state.current_thought


def test_tick_once_late_chain_stage_prefers_consolidation_thought():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    root = goals.save_goal(
        Goal(
            title="继续消化自己刚经历的状态：整理今天的对话",
            source="清晨很安静，我还惦记着“整理今天的对话记忆”。",
            status=GoalStatus.COMPLETED,
            chain_id="chain-1",
            generation=0,
        )
    )
    middle = goals.save_goal(
        Goal(
            title="继续推进：继续消化自己刚经历的状态：整理今天的对话",
            source=root.source,
            status=GoalStatus.COMPLETED,
            chain_id="chain-1",
            parent_goal_id=root.id,
            generation=1,
        )
    )
    leaf = goals.save_goal(
        Goal(
            title="继续推进：继续推进：继续消化自己刚经历的状态：整理今天的对话",
            source=root.source,
            status=GoalStatus.ACTIVE,
            chain_id="chain-1",
            parent_goal_id=middle.id,
            generation=2,
        )
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[leaf.id]))
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "第3步" in state.current_thought
    assert "回看" in state.current_thought


def test_tick_once_completion_thought_reflects_calm_world_state():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="整理今天的对话记忆",
            source="最近总在想星星和夜空",
            status=GoalStatus.COMPLETED,
        )
    )
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            active_goal_ids=[goal.id],
        )
    )
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "松" in state.current_thought
    assert "整理今天的对话记忆" in state.current_thought


def test_tick_once_completed_chain_goal_mentions_next_chain_step():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="继续消化自己刚经历的状态：整理今天的对话",
            source="清晨很安静，我还惦记着“整理今天的对话记忆”。",
            status=GoalStatus.COMPLETED,
            chain_id="chain-1",
            generation=0,
        )
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "第2步" in state.current_thought
    assert "接下来" in state.current_thought


def test_tick_once_records_world_event_into_memory():
    now = datetime(2026, 4, 4, 23, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(Goal(title="整理今天的对话记忆", status=GoalStatus.ACTIVE))
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    loop.tick_once()
    recent = list(reversed(repo.list_recent(limit=5)))
    world_events = [event for event in recent if event.kind == "world"]

    assert len(world_events) == 1
    assert "整理今天的对话记忆" in world_events[0].content


def test_tick_once_records_inner_stage_memory_when_chain_progress_changes():
    first_now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    second_now = first_now + timedelta(seconds=61)
    times = iter([first_now, second_now])
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="继续推进：继续推进：整理今天的对话记忆",
            status=GoalStatus.ACTIVE,
            chain_id="chain-1",
            generation=2,
        )
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: next(times))

    loop.tick_once()
    first_inner_events = [event for event in reversed(repo.list_recent(limit=10)) if event.kind == "inner"]

    loop.tick_once()
    second_inner_events = [event for event in reversed(repo.list_recent(limit=10)) if event.kind == "inner"]

    assert len(first_inner_events) == 1
    assert "第3步" in first_inner_events[0].content
    assert "收束阶段" in first_inner_events[0].content
    assert len(second_inner_events) == 1


def test_tick_once_compresses_inner_stage_memories_into_autobio_memory():
    now = datetime(2026, 4, 4, 16, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="继续推进：继续推进：整理今天的对话记忆",
            status=GoalStatus.ACTIVE,
            chain_id="chain-1",
            generation=2,
        )
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="inner", content="我感觉自己已经走到第1步，正在进入起步阶段。"))
    repo.save_event(MemoryEvent(kind="inner", content="我感觉自己已经走到第2步，正在进入深入阶段。"))
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    loop.tick_once()
    autobio_events = [event for event in reversed(repo.list_recent(limit=10)) if event.kind == "autobio"]

    assert len(autobio_events) == 1
    assert "第1步" in autobio_events[0].content
    assert "第2步" in autobio_events[0].content
    assert "第3步" in autobio_events[0].content
    assert "一路" in autobio_events[0].content


def test_tick_once_does_not_duplicate_world_event_within_cooldown():
    now = datetime(2026, 4, 4, 23, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(Goal(title="整理今天的对话记忆", status=GoalStatus.ACTIVE))
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(
            kind="world",
            content="夜里很安静，我有点困，但还惦记着整理今天的对话记忆。",
            created_at=now - timedelta(minutes=10),
        )
    )
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    loop.tick_once()
    recent = list(reversed(repo.list_recent(limit=5)))
    world_events = [event for event in recent if event.kind == "world"]

    assert len(world_events) == 1


def test_tick_once_generates_goal_from_latest_world_event_when_no_user_topic():
    now = datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc)
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(
            kind="world",
            content="清晨很安静，我还在留意眼前这件事，我还惦记着“整理今天的对话记忆”。",
            created_at=now - timedelta(minutes=40),
        )
    )
    goals = InMemoryGoalRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()
    active_goals = goals.list_active_goals()

    assert len(active_goals) == 1
    assert active_goals[0].chain_id is not None
    assert active_goals[0].parent_goal_id is None
    assert active_goals[0].generation == 0
    assert "整理今天的对话记忆" in active_goals[0].source
    assert state.active_goal_ids == [active_goals[0].id]
    assert "整理今天的对话记忆" in state.current_thought


def test_tick_once_completed_chain_goal_spawns_next_generation_goal():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="继续消化自己刚经历的状态：整理今天的对话",
            source="清晨很安静，我还惦记着“整理今天的对话记忆”。",
            status=GoalStatus.COMPLETED,
            chain_id="chain-1",
            generation=0,
        )
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()
    all_goals = goals.list_goals()
    child_goals = [item for item in all_goals if item.parent_goal_id == goal.id]

    assert len(child_goals) == 1
    child = child_goals[0]
    assert child.chain_id == "chain-1"
    assert child.generation == 1
    assert child.status == GoalStatus.ACTIVE
    assert state.active_goal_ids == [child.id]
    assert state.current_thought is not None
    assert "继续" in state.current_thought


def test_tick_once_executes_first_morning_plan_step_before_regular_goal_focus():
    first_now = datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc)
    second_now = first_now + timedelta(seconds=10)
    third_now = first_now + timedelta(seconds=61)
    times = iter([first_now, second_now, third_now])
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(
        Goal(
            title="整理今天的对话记忆",
            source="清晨很安静，我还惦记着“整理今天的对话记忆”。",
            status=GoalStatus.ACTIVE,
        )
    )
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.MORNING_PLAN,
            active_goal_ids=[goal.id],
            today_plan={
                "goal_id": goal.id,
                "goal_title": goal.title,
                "steps": [
                    {"content": f"把“{goal.title}”的轮廓理一下", "status": "pending"},
                    {"content": "开始动手推进", "status": "pending"},
                ],
            },
        )
    )
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: next(times))

    first_state = loop.tick_once()
    second_state = loop.tick_once()
    third_state = loop.tick_once()

    assert first_state.current_thought is not None
    assert "轮廓理一下" in first_state.current_thought
    assert first_state.focus_mode == FocusMode.MORNING_PLAN
    assert first_state.today_plan is not None
    assert [step.status for step in first_state.today_plan.steps] == ["completed", "pending"]

    assert second_state.current_thought is not None
    assert "开始动手推进" in second_state.current_thought
    assert second_state.focus_mode == FocusMode.AUTONOMY
    assert second_state.today_plan is not None
    assert [step.status for step in second_state.today_plan.steps] == ["completed", "completed"]

    assert third_state.current_thought is not None
    assert goal.title in third_state.current_thought
    assert "开始动手推进" not in third_state.current_thought
    assert third_state.focus_mode == FocusMode.AUTONOMY

    autobio_events = [event for event in reversed(repo.list_recent(limit=10)) if event.kind == "autobio"]
    assert len(autobio_events) == 1
    assert "今天的计划" in autobio_events[0].content
    assert goal.title in autobio_events[0].content


def test_tick_once_executes_safe_command_for_actionable_goal():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(Goal(title="看看现在在哪个目录"))
    store = StateStore(BeingState(mode=WakeMode.AWAKE, active_goal_ids=[goal.id]))
    repo = InMemoryMemoryRepository()
    runner = StubCommandRunner({"pwd": "/Users/ldy/Desktop/map/ai"})
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now, command_runner=runner)

    state = loop.tick_once()

    assert runner.commands == ["pwd"]
    assert state.current_thought is not None
    assert "pwd" in state.current_thought
    assert "/Users/ldy/Desktop/map/ai" in state.current_thought
    assert state.last_action is not None
    assert state.last_action.command == "pwd"
    assert state.last_action.output == "/Users/ldy/Desktop/map/ai"
    action_events = [event for event in reversed(repo.list_recent(limit=10)) if event.kind == "action"]
    assert len(action_events) == 1
    assert "pwd" in action_events[0].content


def test_tick_once_executes_action_step_declared_in_today_plan():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    goals = InMemoryGoalRepository()
    goal = goals.save_goal(Goal(title="晨间检查"))
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.MORNING_PLAN,
            active_goal_ids=[goal.id],
            today_plan={
                "goal_id": goal.id,
                "goal_title": goal.title,
                "steps": [
                    {
                        "content": "先看一下当前目录",
                        "status": "pending",
                        "kind": "action",
                        "command": "pwd",
                    },
                    {
                        "content": "确认接下来要做什么",
                        "status": "pending",
                        "kind": "reflect",
                    },
                ],
            },
        )
    )
    repo = InMemoryMemoryRepository()
    runner = StubCommandRunner({"pwd": "/Users/ldy/Desktop/map/ai"})
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now, command_runner=runner)

    state = loop.tick_once()

    assert runner.commands == ["pwd"]
    assert state.last_action is not None
    assert state.last_action.command == "pwd"
    assert state.today_plan is not None
    assert state.today_plan.steps[0].status == "completed"


def test_tick_once_enters_self_improvement_when_test_failure_is_detected():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    store = StateStore(BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.AUTONOMY))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="self_check", content="测试失败：自主循环没有把计划第一步变成行动。"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.focus_mode == FocusMode.SELF_IMPROVEMENT
    assert state.self_improvement_job is not None
    assert state.self_improvement_job.status == SelfImprovementStatus.DIAGNOSING
    assert "自我编程" in state.current_thought
    assert "测试失败" in state.self_improvement_job.reason


def test_tick_once_can_proactively_enter_self_improvement_after_repeated_idle_progress():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            active_goal_ids=["goal-1"],
        )
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="inner", content="我还在想怎么推进。"))
    repo.save_event(MemoryEvent(kind="chat", role="assistant", content="我先整理一下思路。"))
    repo.save_event(MemoryEvent(kind="autobio", content="今天一直停留在想法里。"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.focus_mode == FocusMode.SELF_IMPROVEMENT
    assert state.self_improvement_job is not None
    assert state.self_improvement_job.reason == "连续多次只产生 thought，没有形成有效行动结果。"


def test_tick_once_respects_self_improvement_cooldown_for_proactive_trigger():
    now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            active_goal_ids=["goal-1"],
            self_improvement_job={
                "reason": "之前已经做过一次自我编程",
                "target_area": "agent",
                "status": "applied",
                "spec": "减少空转",
                "cooldown_until": now + timedelta(hours=1),
            },
        )
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="inner", content="我还在想怎么推进。"))
    repo.save_event(MemoryEvent(kind="chat", role="assistant", content="我先整理一下思路。"))
    repo.save_event(MemoryEvent(kind="autobio", content="今天一直停留在想法里。"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.focus_mode != FocusMode.SELF_IMPROVEMENT
    assert state.self_improvement_job is not None
    assert state.self_improvement_job.status == SelfImprovementStatus.APPLIED
