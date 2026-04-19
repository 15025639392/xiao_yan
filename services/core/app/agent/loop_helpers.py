from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.domain.models import FocusMode, WakeMode
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


def build_defer_checkin_messages(content: str, now: datetime, world_state) -> list[str]:
    prefix = f"{_time_prefix(now)}{_world_tone(world_state)}"
    normalized = content.strip()

    if _looks_emotional(normalized):
        first = f"{prefix}我记着你刚才那句“{normalized}”。"
        second = "你要是现在不想展开也没关系，等你方便时我们再聊。"
        return _deliver_as_split_or_single(first, second, normalized, world_state)

    if _looks_stuck(normalized):
        first = f"{prefix}我记着你刚才提到的“{normalized}”。"
        second = "这会儿不着急做决定，你想好了再继续就行。"
        return _deliver_as_split_or_single(first, second, normalized, world_state)

    return [f"{prefix}我记着你刚才提到的“{normalized}”，如果你现在不方便，不回复也没关系。"]


def build_focus_thought(
    focus_title: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    return f"{_time_prefix(now)}{_world_tone(world_state)}我还惦记着“{focus_title}”，{progress}想继续把它推进。"


def build_action_result_thought(focus_title: str, now: datetime, world_state, result) -> str:
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我刚为“{focus_title}”执行了 `{result.command}`，结果是：{result.output}。"
    )


def build_focus_completion(
    focus_title: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
    next_focus_title: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    if next_focus_title is not None:
        return (
            f"{_time_prefix(now)}{_world_tone(world_state)}"
            f"我把“{focus_title}”先收住了，{progress}接下来想继续“{next_focus_title}”。"
        )
    return f"{_time_prefix(now)}{_world_tone(world_state)}我把“{focus_title}”先收住了。"


def build_chain_consolidation(
    focus_title: str,
    now: datetime,
    world_state,
    chain_progress: str | None = None,
) -> str:
    progress = "" if chain_progress is None else f"{chain_progress}"
    return (
        f"{_time_prefix(now)}{_world_tone(world_state)}"
        f"我想先回看一下，{progress}看看怎么把“{focus_title}”收束得更完整。"
    )


def build_focus_title(content: str) -> str:
    return f"持续理解用户最近在意的话题：{content[:24]}"


def build_next_focus_title(focus_title: str) -> str:
    return f"继续推进：{focus_title[:24]}"


def build_inner_stage_memory(world_state, focus_title: str | None = None) -> str:
    stage_label = _focus_stage_label(world_state.focus_stage)
    focus_suffix = "" if focus_title is None else f"，还在围绕“{focus_title}”"
    return (
        f"我感觉自己已经走到第{world_state.focus_step}步，"
        f"正在进入{stage_label}{focus_suffix}。"
    )


def build_autobio_memory(inner_events: list[MemoryEvent]) -> str:
    steps = [extract_focus_step(event.content) for event in inner_events]
    rendered_steps = "、".join(f"第{step}步" for step in steps if step is not None)
    return f"我最近像是一路从{rendered_steps}走过来，开始学着把这些变化连成自己的经历。"


def next_focus_mode(mode, current_focus_mode):
    if mode != WakeMode.AWAKE:
        return FocusMode.SLEEPING
    return current_focus_mode if current_focus_mode == FocusMode.AUTONOMY else FocusMode.AUTONOMY


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


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


def _deliver_as_split_or_single(
    first: str,
    second: str,
    content: str,
    world_state,
) -> list[str]:
    if _prefer_split_delivery(content, world_state):
        return [first, second]
    return [f"{first}{second}"]


def _prefer_split_delivery(content: str, world_state) -> bool:
    # 语境更重、更复杂时，拆分两条可以更自然也更易读；轻量语境则合并一条避免刷屏。
    if len(content) >= 16:
        return True
    if "，" in content or "。" in content or "？" in content or "!" in content or "！" in content:
        return True
    if world_state.focus_tension == "high":
        return True
    return False
