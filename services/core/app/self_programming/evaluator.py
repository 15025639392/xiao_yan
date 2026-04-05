from datetime import datetime, timedelta

from app.domain.models import BeingState, FocusMode, WakeMode
from app.memory.models import MemoryEvent
from app.self_programming.models import SelfProgrammingCandidate, SelfProgrammingTrigger


class SelfProgrammingEvaluator:
    PROACTIVE_EVENT_THRESHOLD = 2

    def evaluate(
        self,
        state: BeingState,
        recent_events: list[MemoryEvent],
        now: datetime,
    ) -> SelfProgrammingCandidate | None:
        if state.mode != WakeMode.AWAKE:
            return None
        if state.focus_mode == FocusMode.SELF_IMPROVEMENT:
            return None
        if (
            state.self_programming_job is not None
            and state.self_programming_job.cooldown_until is not None
            and now < state.self_programming_job.cooldown_until
        ):
            return None

        hard_signal = next(
            (
                event
                for event in recent_events
                if event.kind == "self_check" or "测试失败" in event.content
            ),
            None,
        )
        if hard_signal is not None:
            return SelfProgrammingCandidate(
                trigger=SelfProgrammingTrigger.HARD_FAILURE,
                reason=hard_signal.content,
                target_area=_infer_target_area(hard_signal.content),
                spec=_build_hard_failure_spec(hard_signal.content),
                test_commands=_default_test_commands(_infer_target_area(hard_signal.content)),
                created_at=now,
            )

        if state.focus_mode != FocusMode.AUTONOMY:
            return None

        if state.last_action is not None:
            return None

        internal_events = [
            event
            for event in recent_events
            if event.kind in {"chat", "autobio"} and event.role != "user"
        ]
        if len(internal_events) < self.PROACTIVE_EVENT_THRESHOLD:
            return None

        recent_internal = internal_events[: self.PROACTIVE_EVENT_THRESHOLD]
        if any(event.kind == "action" for event in recent_internal):
            return None

        if not state.active_goal_ids:
            return None

        return SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.PROACTIVE,
            reason="连续多次只产生 thought，没有形成有效行动结果。",
            target_area="agent",
            spec="减少自主循环空转，提升从 thought 到 action 的推进力度。",
            test_commands=_default_test_commands("agent"),
            created_at=now,
        )


def _infer_target_area(reason: str) -> str:
    if "前端" in reason or "状态面板" in reason or "UI" in reason:
        return "ui"
    if "计划" in reason:
        return "planning"
    return "agent"


def _build_hard_failure_spec(reason: str) -> str:
    return f"修复当前硬故障：{reason}"


def _default_test_commands(target_area: str) -> list[str]:
    if target_area == "ui":
        return [
            "npm test -- --run src/App.test.tsx src/components/StatusPanel.test.tsx",
        ]
    if target_area == "planning":
        return ["pytest tests/test_morning_plan_planner.py -q"]
    return ["pytest tests/test_autonomy_loop.py -q"]
