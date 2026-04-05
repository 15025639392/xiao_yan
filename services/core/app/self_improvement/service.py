from datetime import datetime
import logging

from app.domain.models import BeingState, FocusMode, SelfImprovementStatus
from app.memory.models import MemoryEvent
from app.self_improvement.evaluator import SelfImprovementEvaluator
from app.self_improvement.executor import SelfImprovementExecutor
from app.self_improvement.history_store import SelfImprovementHistory
from app.self_improvement.health_checker import (
    HealthChecker,
    HealthSignal,
    HealthReport,
    HealthGrade,
)
from app.self_improvement.rollback_recovery import RollbackReason
from typing import TYPE_CHECKING, Protocol, Any

if TYPE_CHECKING:
    class _PlannerProto(Protocol):
        def plan(self, candidate) -> ...: ...

        def plan_all(self, candidate) -> list: ...


logger = logging.getLogger(__name__)


class SelfImprovementService:
    def __init__(
        self,
        evaluator: SelfImprovementEvaluator | None = None,
        planner = None,
        executor: SelfImprovementExecutor | None = None,
        # Phase 5: 可选的健康检查器和历史记录
        health_checker: HealthChecker | None = None,
        history: SelfImprovementHistory | None = None,
    ) -> None:
        self.evaluator = evaluator or SelfImprovementEvaluator()
        self.planner = planner  # type: ignore[assignment]
        self.executor = executor
        # Phase 5: 健康检查器（可选注入）
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
                "self_improvement_job": job,
                "current_thought": (
                    f'我觉得自己在"{job.target_area}"这块还不够好，先停下来做一次自我编程：{job.reason}'
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

            # Phase 4: 应用前预检（冲突检测 + 沙箱预验证）
            recent_history = getattr(self, 'history', None)
            history_list = recent_history.get_recent(10) if recent_history else None
            checked_job = self.executor.preflight_check(job, recent_history=history_list)

            # 如果预检被阻塞或失败，直接结束
            if checked_job.status == SelfImprovementStatus.FAILED:
                return _finish_state(state, checked_job)

            job = checked_job  # 用通过预检的 Job 继续

            # Phase 2: 尝试多候选 A/B 测试（如果 planner 支持 plan_all）
            result = self._try_multi_candidate(state, job)
            if result is not None:
                return result

            # Phase 6: 应用后进入审批等待状态（而非直接 VERIFYING）
            next_job = self.executor.apply(job)
            if next_job.status == SelfImprovementStatus.VERIFYING:
                # 将 VERIFYING 降级为 PENDING_APPROVAL，等待用户审批
                approval_edits_summary = _build_edits_summary(next_job)
                pending_job = next_job.model_copy(
                    update={
                        "status": SelfImprovementStatus.PENDING_APPROVAL,
                        "approval_requested_at": datetime.now(),
                        "approval_edits_summary": approval_edits_summary,
                    }
                )
                return state.model_copy(
                    update={
                        "self_improvement_job": pending_job,
                        "current_thought": (
                            f"我已经为 {job.target_area} 准备好了补丁，"
                            f"修改了 {len(next_job.touched_files)} 个文件。"
                            "正在等待审批..."
                        ),
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

            # Phase 3: APPLIED 后自动 Git commit
            if next_job.status == SelfImprovementStatus.APPLIED and self.executor.git is not None:
                next_job = self.executor.commit_job(next_job)

            # Phase 4: 记录成功历史 + 更新冲突检测器
            if next_job.status == SelfImprovementStatus.APPLIED:
                self.executor.record_successful_apply(next_job)
                if hasattr(self, 'history') and self.history is not None:
                    self.history.record_from_job(next_job)

                # Phase 5: 健康度评估（非阻塞，只做记录和标记）
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
                    logger.debug(f"Phase 5 health check skipped: {exc}")

            return _finish_state(state, next_job)

        if job.status in {SelfImprovementStatus.APPLIED, SelfImprovementStatus.FAILED, SelfImprovementStatus.REJECTED}:
            return _finish_state(state, job)

        # Phase 6: PENDING_APPROVAL 状态 — 等待用户操作，不自动推进
        if job.status == SelfImprovementStatus.PENDING_APPROVAL:
            # 不自动 tick，保持等待状态（由 API 端点触发状态变更）
            return None

        return None

    def _try_multi_candidate(self, state: BeingState, job) -> BeingState | None:
        """Phase 2: 如果 planner 支持 plan_all，尝试多候选 A/B 测试。

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
            if best.status == SelfImprovementStatus.APPLIED:
                return _finish_state(state, best)
            return state.model_copy(
                update={
                    "self_improvement_job": best,
                    "current_thought": thought,
                }
            )

        # 所有候选都失败
        failed_job = job.model_copy(
            update={
                "status": SelfImprovementStatus.FAILED,
                "patch_summary": f"所有 {len(candidates)} 个候选方案均未通过验证。",
            }
        )
        return _finish_state(state, failed_job)


def _reconstruct_candidate(job) -> object:
    """从 Job 反推一个 Candidate 对象，用于调用 plan_all。

    这是一个轻量级重构——只提取必要字段。
    """
    from app.self_improvement.models import SelfImprovementCandidate, SelfImprovementTrigger

    # 根据 patch_summary 判断触发类型
    trigger_type = SelfImprovementTrigger.PROACTIVE
    if "[LLM]" in (job.patch_summary or ""):
        trigger_type = SelfImprovementTrigger.HARD_FAILURE

    test_commands = []
    if job.verification and job.verification.commands:
        test_commands = job.verification.commands

    return SelfImprovementCandidate(
        trigger=trigger_type,
        reason=job.reason,
        target_area=job.target_area,
        spec=job.spec,
        test_commands=test_commands,
    )


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


# ── Phase 5: 健康度评估辅助方法 ──────────────────────


def _evaluate_health(self, job: Any) -> HealthReport | None:
    """SelfImprovementHealthCheck._evaluate_health 的辅助方法（在类内部调用）。

    Args:
        job: 刚通过验证的 SelfImprovementJob

    Returns:
        健康报告，或 None
    """
    checker = self.health_checker if hasattr(self, 'health_checker') else None
    if checker is None:
        return None

    # 从历史记录中收集数据
    history_list = []
    recent_rollbacks = 0
    recent_conflicts = 0

    if hasattr(self, 'history') and self.history is not None:
        try:
            history_list = self.history.get_recent(20)
            # 统计回滚和冲突次数
            for entry in history_list:
                status_val = getattr(entry, 'status', '')
                if hasattr(status_val, 'value'):
                    status_val = status_val.value
                if status_val == 'rolled_back':
                    recent_rollbacks += 1
                conflict_count = getattr(entry, 'conflict_count', 0)
                if conflict_count > 0:
                    recent_conflicts += 1
        except Exception:
            pass  # 历史数据不可用时跳过

    # 构建健康信号
    signals: list[HealthSignal] = []

    # 从 verification 结果提取测试通过率信号
    if job.verification and job.verification.passed:
        signals.append(HealthSignal(
            source="verification",
            metric="test_pass_rate",
            value=100.0,
            unit="%",
        ))
    elif job.verification and not job.verification.passed:
        signals.append(HealthSignal(
            source="verification",
            metric="test_pass_rate",
            value=0.0,
            unit="%",
        ))

    # 执行评估
    report = checker.check(
        signals=signals if signals else None,
        history=history_list if history_list else None,
        recent_rollbacks=recent_rollbacks,
        recent_conflicts=recent_conflicts,
    )

    logger.info(
        f"Phase 5 health check for {job.id[:12]}: "
        f"{report.summary}"
    )

    return report


def _build_edits_summary(job: Any) -> str:
    """生成编辑摘要，供审批面板展示。

    Args:
        job: 已 apply（VERIFYING 状态）的 Job

    Returns:
        人类可读的编辑摘要
    """
    edits = job.edits or []
    touched = job.touched_files or []
    if not edits and not touched:
        return job.patch_summary or job.spec[:120]

    kind_counts: dict[str, int] = {}
    for e in edits:
        k = getattr(e, 'kind', 'replace')
        kind_counts[k] = kind_counts.get(k, 0) + 1

    parts = []
    if kind_counts:
        for k, c in kind_counts.items():
            parts.append(f"{k.upper()}×{c}")
    if touched:
        parts.append(f"文件: {', '.join(touched[:5])}")

    return " | ".join(parts) if parts else (job.patch_summary or job.spec[:120])
