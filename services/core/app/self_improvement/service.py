from datetime import datetime

from app.domain.models import BeingState, FocusMode, SelfImprovementStatus
from app.memory.models import MemoryEvent
from app.self_improvement.evaluator import SelfImprovementEvaluator
from app.self_improvement.executor import SelfImprovementExecutor
from app.self_improvement.planner import SelfImprovementPlanner


class SelfImprovementService:
    def __init__(
        self,
        evaluator: SelfImprovementEvaluator | None = None,
        planner: SelfImprovementPlanner | None = None,
        executor: SelfImprovementExecutor | None = None,
    ) -> None:
        self.evaluator = evaluator or SelfImprovementEvaluator()
        self.planner = planner or SelfImprovementPlanner()
        self.executor = executor

    def maybe_start_job(
        self,
        state: BeingState,
        recent_events: list[MemoryEvent],
        now: datetime,
    ) -> BeingState | None:
        if state.focus_mode == FocusMode.SELF_IMPROVEMENT:
            return None

        candidate = self.evaluator.evaluate(state, recent_events, now)
        if candidate is None:
            return None

        job = self.planner.plan(candidate)
        return state.model_copy(
            update={
                "focus_mode": FocusMode.SELF_IMPROVEMENT,
                "self_improvement_job": job,
                "current_thought": (
                    f"我觉得自己在“{job.target_area}”这块还不够好，先停下来做一次自我编程：{job.reason}"
                ),
            }
        )

    def tick_job(self, state: BeingState) -> BeingState | None:
        job = state.self_improvement_job
        if state.focus_mode != FocusMode.SELF_IMPROVEMENT or job is None:
            return None

        if job.status == SelfImprovementStatus.DIAGNOSING:
            return state.model_copy(
                update={
                    "self_improvement_job": job.model_copy(
                        update={"status": SelfImprovementStatus.PATCHING}
                    ),
                    "current_thought": f"我先把这次自我编程收敛成一个小补丁：{job.spec}",
                }
            )

        if job.status == SelfImprovementStatus.PATCHING:
            if self.executor is None:
                next_job = job.model_copy(
                    update={
                        "status": SelfImprovementStatus.FAILED,
                        "patch_summary": "没有可用的自我编程执行器。",
                    }
                )
                return _finish_state(state, next_job)
            next_job = self.executor.apply(job)
            if next_job.status == SelfImprovementStatus.VERIFYING:
                return state.model_copy(
                    update={
                        "self_improvement_job": next_job,
                        "current_thought": "补丁已经写进去了，接下来跑测试确认这次自改有没有站住。",
                    }
                )
            return _finish_state(state, next_job)

        if job.status == SelfImprovementStatus.VERIFYING:
            if self.executor is None:
                next_job = job.model_copy(
                    update={
                        "status": SelfImprovementStatus.FAILED,
                        "patch_summary": "没有可用的自我编程执行器。",
                    }
                )
                return _finish_state(state, next_job)
            next_job = self.executor.verify(job)
            return _finish_state(state, next_job)

        if job.status in {SelfImprovementStatus.APPLIED, SelfImprovementStatus.FAILED}:
            return _finish_state(state, job)

        return None


def _finish_state(state: BeingState, job) -> BeingState:
    if job.status == SelfImprovementStatus.APPLIED:
        thought = f"这次自我编程通过了验证，我刚补强了 {job.target_area}。"
    else:
        thought = f"这次自我编程没有通过验证，我先记住问题：{job.patch_summary or job.reason}"
    return state.model_copy(
        update={
            "focus_mode": FocusMode.AUTONOMY,
            "self_improvement_job": job,
            "current_thought": thought,
        }
    )
