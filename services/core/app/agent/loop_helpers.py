from __future__ import annotations

import string
from datetime import datetime
from pathlib import Path

from app.agent.autonomy import GoalFocusSummary
from app.domain.models import FocusMode, TodayPlanStepStatus, WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import GoalRepository
from app.memory.models import MemoryEvent


def build_proactive_thought(recent_events, now: datetime, world_state) -> str:
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)
    if recent_events:
        return f"{prefix}{tone}我在想刚才关于“{recent_events[-1].content}”的事。"
    return f"{prefix}{tone}我在整理现在的状态，看看要不要主动说点什么。"


def find_latest_user_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "chat" and event.role == "user":
            return event
    return None


def find_latest_world_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "world":
            return event
    return None


def find_latest_inner_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "inner":
            return event
    return None


def find_latest_autobio_event(recent_events):
    for event in reversed(recent_events):
        if event.kind == "autobio":
            return event
    return None


def build_proactive_message(content: str, now: datetime, world_state) -> str:
    prefix = f"{_time_prefix(now)}{_world_tone(world_state)}"
    normalized = content.strip()

    if _looks_emotional(normalized):
        return (
            f"{prefix}我还挂着你刚才那句“{normalized}”。"
            "先别把自己逼得太紧，我们先只把眼前这一小段撑过去就好。"
        )

    if _looks_stuck(normalized):
        return (
            f"{prefix}你刚才说“{normalized}”，我心里一直没放下。"
            "先别急着一下子想清全部，我们先抓一个最小的一步就够了。"
        )

    if _looks_relational_or_memory_cue(normalized):
        return (
            f"{prefix}我还记得你提到的“{normalized}”。"
            "这种被再次想起的感觉，让我更想把它接住一点。"
        )

    return (
        f"{prefix}我刚刚又想到你提到的“{normalized}”。"
        "我想先把这点念头递给你，免得它又从我心里滑过去。"
    )


def build_goal_focus(
    goal: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    return f"{_time_prefix(now)}{_world_tone(world_state)}我还惦记着“{goal}”，{progress}想继续把它推进。"


def build_today_plan_step_focus(
    goal: str,
    step_content: str,
    now: datetime,
    world_state,
) -> str:
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我先按今天的计划，从第一步开始：{step_content}。"
    )


def build_today_plan_completion_memory(goal: str) -> str:
    return f"我把今天的计划“{goal}”完整走完了，感觉这一轮心里更有数了。"


def build_action_result_thought(goal: str, now: datetime, world_state, result) -> str:
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我刚为“{goal}”执行了 `{result.command}`，结果是：{result.output}。"
    )


def build_goal_completion(
    goal: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
    next_goal_title: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    if next_goal_title is not None:
        return (
            f"{_time_prefix(now)}{_world_tone(world_state)}"
            f"我把“{goal}”先收住了，{progress}接下来想继续“{next_goal_title}”。"
        )
    return f"{_time_prefix(now)}{_world_tone(world_state)}我把“{goal}”先收住了。"


def build_chain_consolidation(
    goal: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我想先回看一下，{progress}看看怎么把“{goal}”收束得更完整。"
    )


def build_goal_title(content: str) -> str:
    return f"持续理解用户最近在意的话题：{content[:24]}"


def build_world_goal_title(content: str) -> str:
    return f"继续消化自己刚经历的状态：{content[:24]}"


def build_next_goal_title(goal_title: str) -> str:
    return f"继续推进：{goal_title[:24]}"


def build_world_goal_start(content: str, now: datetime, world_state) -> str:
    return f"{_time_prefix(now)}{_world_tone(world_state)}我还在回味刚才那件事：“{content}”。"


def is_generated_goal_id(value: str | None) -> bool:
    if value is None or len(value) != 32:
        return False
    return all(char in string.hexdigits for char in value)


def display_goal_title(goal_id: str | None, goal: Goal | None) -> str | None:
    if goal is not None:
        return goal.title
    if goal_id is None or is_generated_goal_id(goal_id):
        return None
    return goal_id


def build_inner_stage_memory(world_state, goal_title: str | None = None) -> str:
    stage_label = _focus_stage_label(world_state.focus_stage)
    goal_suffix = "" if goal_title is None else f"，还在围绕“{goal_title}”"
    return (
        f"我感觉自己已经走到第{world_state.focus_step}步，"
        f"正在进入{stage_label}{goal_suffix}。"
    )


def build_autobio_memory(inner_events: list[MemoryEvent]) -> str:
    steps = [extract_focus_step(event.content) for event in inner_events]
    rendered_steps = "、".join(f"第{step}步" for step in steps if step is not None)
    return f"我最近像是一路从{rendered_steps}走过来，开始学着把这些变化连成自己的经历。"


def sync_today_plan(today_plan, active_goal_ids: list[str]):
    if today_plan is None:
        return None
    if today_plan.goal_id not in active_goal_ids:
        return None
    return today_plan


def next_focus_mode(mode, current_focus_mode, today_plan):
    if mode != WakeMode.AWAKE:
        return FocusMode.SLEEPING
    if current_focus_mode == FocusMode.SELF_IMPROVEMENT:
        return FocusMode.SELF_IMPROVEMENT
    if today_plan is None:
        return FocusMode.AUTONOMY
    if any(step.status == TodayPlanStepStatus.PENDING for step in today_plan.steps):
        return FocusMode.MORNING_PLAN
    return current_focus_mode if current_focus_mode == FocusMode.AUTONOMY else FocusMode.AUTONOMY


def build_chain_progress(goal_repository: GoalRepository, goal: Goal) -> str | None:
    summary = summarize_chain(goal_repository, goal)
    if summary is None:
        return None
    return f"这条线已经走到第{summary.generation + 1}步了，"


def build_chain_transition(goal_repository: GoalRepository, goal: Goal) -> str | None:
    summary = summarize_chain(goal_repository, goal)
    if summary is None:
        return None
    return f"这条线已经接到第{summary.generation + 1}步了，"


def build_self_programming_memory(job) -> str:
    if job.status.value == "applied":
        return f"我刚完成了一次自我编程，补强了 {job.target_area}，并通过了验证。"
    return f"我刚尝试自我编程，但还没通过验证：{job.patch_summary or job.reason}"


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_goal_focus_summary(
    goal_repository: GoalRepository,
    goal: Goal,
) -> GoalFocusSummary:
    if goal.chain_id is None:
        return GoalFocusSummary(goal_title=goal.title)

    chain_goals = [item for item in goal_repository.list_goals() if item.chain_id == goal.chain_id]
    chain_length = len(chain_goals)
    generation = goal.generation
    stage = _chain_stage_for(generation)

    return GoalFocusSummary(
        goal_title=goal.title,
        chain_id=goal.chain_id,
        chain_length=chain_length,
        chain_generation=generation,
        stage=stage,
    )


def summarize_chain(goal_repository: GoalRepository, goal: Goal):
    if goal.chain_id is None:
        return None

    chain_goals = sort_goals_by_generation([item for item in goal_repository.list_goals() if item.chain_id == goal.chain_id])
    if not chain_goals:
        return None

    highest_generation = max(item.generation for item in chain_goals)
    latest_generation_goals = [item for item in chain_goals if item.generation == highest_generation]
    return sorted(
        latest_generation_goals,
        key=lambda item: _goal_status_priority(item.status),
    )[0]


def sort_goals_by_generation(goals: list[Goal]) -> list[Goal]:
    return sorted(goals, key=lambda goal: (goal.generation, goal.created_at))


def _goal_status_priority(status: GoalStatus) -> int:
    if status == GoalStatus.ACTIVE:
        return 0
    if status == GoalStatus.PAUSED:
        return 1
    if status == GoalStatus.COMPLETED:
        return 2
    return 3


def _chain_stage_for(generation: int) -> str:
    if generation >= 2:
        return "consolidate"
    if generation == 1:
        return "deepen"
    return "start"


def _focus_stage_label(stage: str) -> str:
    if stage == "consolidate":
        return "收束阶段"
    if stage == "deepen":
        return "深入阶段"
    if stage == "start":
        return "起步阶段"
    return "当前阶段"


def extract_focus_step(content: str) -> int | None:
    marker = "第"
    suffix = "步"
    if marker not in content or suffix not in content:
        return None

    start = content.find(marker) + len(marker)
    end = content.find(suffix, start)
    if end <= start:
        return None

    step_text = content[start:end]
    if not step_text.isdigit():
        return None
    return int(step_text)


def _time_prefix(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上，"
    if 11 <= hour < 17:
        return "白天，"
    if 17 <= hour < 22:
        return "傍晚，"
    return "晚上，"


def _world_tone(world_state) -> str:
    if world_state.mood == "tired":
        return "我有点困，但"
    if world_state.mood == "calm":
        return "我心里松一点了，"
    if world_state.focus_tension == "high":
        return "我心里还绷着这件事，"
    if world_state.energy == "high":
        return "我现在挺清醒，"
    return ""


def _looks_emotional(content: str) -> bool:
    patterns = (
        "累",
        "疲惫",
        "提不起劲",
        "没动力",
        "焦虑",
        "难受",
        "崩",
        "压力",
        "烦",
    )
    return any(pattern in content for pattern in patterns)


def _looks_stuck(content: str) -> bool:
    patterns = (
        "不知道从哪开始",
        "有点乱",
        "卡住",
        "不知道怎么办",
        "理不清",
        "不知道怎么做",
    )
    return any(pattern in content for pattern in patterns)


def _looks_relational_or_memory_cue(content: str) -> bool:
    patterns = (
        "记得",
        "想起",
        "还记得",
        "那天",
        "之前",
    )
    return any(pattern in content for pattern in patterns)
