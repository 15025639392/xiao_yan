from datetime import datetime
import logging

from app.domain.models import BeingState, FocusMode, SelfProgrammingStatus
from app.memory.models import MemoryEvent
from app.self_programming.evaluator import SelfProgrammingEvaluator
from app.self_programming.executor import SelfProgrammingExecutor
from app.self_programming.history_store import SelfProgrammingHistory
from app.self_programming.health_checker import (
    HealthChecker,
    HealthReport,
)
from app.self_programming.rollback_recovery import RollbackReason
from app.self_programming.service_helpers import (
    build_edits_summary as _build_edits_summary,
    finish_state as _finish_state,
    reconstruct_candidate as _reconstruct_candidate,
    evaluate_health,
)
from typing import TYPE_CHECKING, Protocol, Any

if TYPE_CHECKING:
    class _PlannerProto(Protocol):
        def plan(self, candidate) -> ...: ...

        def plan_all(self, candidate) -> list: ...


logger = logging.getLogger(__name__)


class SelfProgrammingService:
    def __init__(
        self,
        evaluator: SelfProgrammingEvaluator | None = None,
        planner = None,
        executor: SelfProgrammingExecutor | None = None,
        # 可选的健康检查器和历史记录
        health_checker: HealthChecker | None = None,
        history: SelfProgrammingHistory | None = None,
    ) -> None:
        self.evaluator = evaluator or SelfProgrammingEvaluator()
        self.planner = planner  # type: ignore[assignment]
        self.executor = executor
        # 健康检查器（可选注入）
        self.health_checker = health_checker or HealthChecker()
        self.history = history  # type: ignore[assignment]

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
                "self_programming_job": job,
                "current_thought": (
                    f'我觉得自己在"{job.target_area}"这块还不够好。'
                    "已生成改进草案，等待你确认开工。"
                ),
            }
        )

    def tick_job(self, state: BeingState) -> BeingState | None:
        job = state.self_programming_job
        if state.focus_mode != FocusMode.SELF_IMPROVEMENT or job is None:
            return None

        if job.status == SelfProgrammingStatus.DRAFTED:
            return None

        if job.status == SelfProgrammingStatus.PENDING_START_APPROVAL:
            return None

        if job.status == SelfProgrammingStatus.QUEUED:
            return None

        if job.status == SelfProgrammingStatus.FROZEN:
            return None

        if job.status == SelfProgrammingStatus.RUNNING:
            job = job.model_copy(
                update={
                    "status": SelfProgrammingStatus.DIAGNOSING,
                    "queue_status": SelfProgrammingStatus.RUNNING.value,
                }
            )

        if job.status == SelfProgrammingStatus.DIAGNOSING:
            return state.model_copy(
                update={
                    "self_programming_job": job.model_copy(
                        update={"status": SelfProgrammingStatus.PATCHING}
                    ),
                    "current_thought": f"我先把这次自我编程收敛成一个小补丁：{job.spec}",
                }
            )

        if job.status == SelfProgrammingStatus.PATCHING:
            if self.executor is None:
                next_job = job.model_copy(
                    update={
                        "status": SelfProgrammingStatus.FAILED,
                        "patch_summary": "没有可用的自我编程执行器。",
                    }
                )
                return _finish_state(state, next_job)

            # 应用前预检（冲突检测 + 沙箱预验证）
            recent_history = getattr(self, 'history', None)
            history_list = recent_history.get_recent(10) if recent_history else None
            checked_job = self.executor.preflight_check(job, recent_history=history_list)

            # 如果预检被阻塞或失败，直接结束
            if checked_job.status == SelfProgrammingStatus.FAILED:
                return _finish_state(state, checked_job)

            job = checked_job  # 用通过预检的 Job 继续

            # 尝试多候选 A/B 测试（如果 planner 支持 plan_all）
            result = self._try_multi_candidate(state, job)
            if result is not None:
                return result

            # 应用后进入审批等待状态（而非直接 VERIFYING）
            next_job = self.executor.apply(job)
            if next_job.status == SelfProgrammingStatus.VERIFYING:
                # 将 VERIFYING 降级为 PENDING_APPROVAL，等待用户审批
                approval_edits_summary = _build_edits_summary(next_job)
                pending_job = next_job.model_copy(
                    update={
                        "status": SelfProgrammingStatus.PENDING_APPROVAL,
                        "approval_requested_at": datetime.now(),
                        "approval_edits_summary": approval_edits_summary,
                    }
                )
                return state.model_copy(
                    update={
                        "self_programming_job": pending_job,
                        "current_thought": (
                            f"我已经为 {job.target_area} 准备好了补丁，"
                            f"修改了 {len(next_job.touched_files)} 个文件。"
                            "正在等待审批..."
                        ),
                    }
                )
            return _finish_state(state, next_job)

        if job.status == SelfProgrammingStatus.VERIFYING:
            if self.executor is None:
                next_job = job.model_copy(
                    update={
                        "status": SelfProgrammingStatus.FAILED,
                        "patch_summary": "没有可用的自我编程执行器。",
                    }
                )
                return _finish_state(state, next_job)
            next_job = self.executor.verify(job)

            # APPLIED 后自动 Git commit
            if next_job.status == SelfProgrammingStatus.APPLIED and self.executor.git is not None:
                next_job = self.executor.commit_job(next_job)

            # 记录成功历史 + 更新冲突检测器
            if next_job.status == SelfProgrammingStatus.APPLIED:
                self.executor.record_successful_apply(next_job)
                if hasattr(self, 'history') and self.history is not None:
                    self.history.record_from_job(next_job)

                # 健康度评估（非阻塞，只做记录和标记）
                try:
                    health_report = self._evaluate_health(next_job)
                    if health_report is not None:
                        next_job = next_job.model_copy(update={
                            "health_score": health_report.overall_score,
                            "health_grade": health_report.grade.value,
                        })
                        # 如果健康度极低，记录回滚建议
                        if health_report.rollback_advised:
                            logger.warning(
                                f"Health check advises rollback for job {next_job.id[:12]}: "
                                f"{health_report.rollback_reason}"
                            )
                            next_job = next_job.model_copy(update={
                                "rollback_info": f"⚠️ 建议回滚: {health_report.rollback_reason}",
                            })
                except Exception as exc:
                    logger.debug(f"Health check skipped: {exc}")

            return _finish_state(state, next_job)

        if job.status in {SelfProgrammingStatus.APPLIED, SelfProgrammingStatus.FAILED, SelfProgrammingStatus.REJECTED}:
            return _finish_state(state, job)

        # PENDING_APPROVAL 状态：等待用户操作，不自动推进
        if job.status == SelfProgrammingStatus.PENDING_APPROVAL:
            # 不自动 tick，保持等待状态（由 API 端点触发状态变更）
            return None

        return None

    def _try_multi_candidate(self, state: BeingState, job) -> BeingState | None:
        """如果 planner 支持 plan_all，尝试多候选 A/B 测试。

        Returns:
            处理后的新状态，或 None（表示不应使用多候选路径）
        """
        # 检查 planner 是否有 plan_all 方法
        if not hasattr(self.planner, "plan_all"):
            return None

        # 从当前状态重建 candidate 信息来获取多候选
        try:
            candidates = self.planner.plan_all(_reconstruct_candidate(job))
        except Exception as exc:
            logger.debug(f"Multi-candidate planning not available: {exc}")
            return None

        if len(candidates) <= 1:
            # 只有 0 或 1 个候选，走普通路径即可
            return None

        # 使用 Executor.try_best 做 A/B 测试
        best = self.executor.try_best(candidates)
        if best is not None:
            thought = (
                f"我评估了 {len(candidates)} 种修复方案，"
                f"最终采用了评分最高的方案，正在验证中。"
            )
            if best.status == SelfProgrammingStatus.APPLIED:
                return _finish_state(state, best)
            return state.model_copy(
                update={
                    "self_programming_job": best,
                    "current_thought": thought,
                }
            )

        # 所有候选都失败
        failed_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.FAILED,
                "patch_summary": f"所有 {len(candidates)} 个候选方案均未通过验证。",
            }
        )
        return _finish_state(state, failed_job)


def _evaluate_health(self, job: Any) -> HealthReport | None:
    return evaluate_health(self, job, logger)
