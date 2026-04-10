from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_persona_service, get_state_store
from app.domain.models import BeingState, FocusMode, SelfProgrammingStatus
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.self_programming.history_models import HistoryEntryStatus
from app.self_programming.history_store import SelfProgrammingHistory
from app.self_programming.rollback_recovery import RollbackReason, RollbackStatus

logger = getLogger(__name__)


class ApprovalRequest(BaseModel):
    reason: str | None = None


class DelegateRequest(BaseModel):
    provider: str | None = "codex"


def build_self_programming_router() -> APIRouter:
    router = APIRouter()

    def _get_history(request: Request) -> SelfProgrammingHistory:
        history = getattr(request.app.state, "self_programming_history", None)
        if history is None:
            history = SelfProgrammingHistory(in_memory=True)
            request.app.state.self_programming_history = history
        return history

    def _get_executor(request: Request):
        loop = getattr(request.app.state, "autonomy_loop", None)
        if loop is None:
            return None
        svc = getattr(loop, "self_programming_service", None)
        if svc is None:
            return None
        return getattr(svc, "executor", None)

    @router.post("/self-programming/{job_id}/request-start")
    def request_start(
        job_id: str,
        request: ApprovalRequest | None = None,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.DRAFTED:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not drafted")
        if not (job.reason_statement and job.reason_statement.strip()):
            raise HTTPException(status_code=400, detail="reason_statement is required before request-start")
        if not (job.direction_statement and job.direction_statement.strip()):
            raise HTTPException(status_code=400, detail="direction_statement is required before request-start")

        next_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.PENDING_START_APPROVAL,
                "queue_status": SelfProgrammingStatus.PENDING_START_APPROVAL.value,
            }
        )
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": next_job,
                    "current_thought": "自我编程草案已提交，等待你确认开工。",
                }
            )
        )
        return {"success": True, "message": "已提交开工申请", "job_id": job_id}

    @router.post("/self-programming/{job_id}/approve-start")
    def approve_start(
        job_id: str,
        request: ApprovalRequest | None = None,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.PENDING_START_APPROVAL:
            raise HTTPException(
                status_code=409,
                detail=f"Job status is {job.status.value}, not pending_start_approval",
            )

        next_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.QUEUED,
                "queue_status": SelfProgrammingStatus.QUEUED.value,
                "start_approval_reason": request.reason if request else None,
                "start_approved_by": "human",
                "start_approved_at": datetime.now(timezone.utc),
                "rejection_phase": None,
                "rejection_reason": None,
            }
        )
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": next_job,
                    "current_thought": "收到开工确认，任务已入队，准备委托专业执行体。",
                }
            )
        )
        return {"success": True, "message": "已确认开工", "job_id": job_id}

    @router.post("/self-programming/{job_id}/reject-start")
    def reject_start(
        job_id: str,
        request: ApprovalRequest,
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.PENDING_START_APPROVAL:
            raise HTTPException(
                status_code=409,
                detail=f"Job status is {job.status.value}, not pending_start_approval",
            )

        rejected_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.DRAFTED,
                "queue_status": SelfProgrammingStatus.DRAFTED.value,
                "rejection_phase": "start",
                "rejection_reason": request.reason or "人工拒绝开工",
                "rejected_by": "human",
                "rejected_at": datetime.now(timezone.utc),
            }
        )
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": rejected_job,
                    "current_thought": _compose_reflective_thought(
                        state.current_thought,
                        summary=f"开工申请被拒了，{rejected_job.target_area} 这块的方案还不够清晰",
                        next_step=f"我会先按反馈重写方向说明。原因：{rejected_job.rejection_reason}",
                    ),
                }
            )
        )
        persona_service.infer_self_programming_emotion("rejected", rejected_job.target_area)
        return {"success": True, "message": "已拒绝开工", "job_id": job_id}

    @router.post("/self-programming/{job_id}/delegate")
    def delegate_job(
        job_id: str,
        request: DelegateRequest | None = None,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.QUEUED:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not queued")

        provider = (request.provider if request else None) or "codex"
        next_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.RUNNING,
                "queue_status": SelfProgrammingStatus.RUNNING.value,
                "delegate_provider": provider,
                "delegate_run_id": job.delegate_run_id or uuid4().hex,
                "execution_workspace": job.execution_workspace or f".self-programming/worktrees/{job.id}",
                "frozen_reason": None,
            }
        )
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": next_job,
                    "current_thought": f"已委托 {provider} 执行自我编程任务，正在运行。",
                }
            )
        )
        return {"success": True, "message": "已开始委托执行", "job_id": job_id}

    @router.post("/self-programming/{job_id}/retry")
    def retry_job(
        job_id: str,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status not in {
            SelfProgrammingStatus.FAILED,
            SelfProgrammingStatus.FROZEN,
            SelfProgrammingStatus.REJECTED,
            SelfProgrammingStatus.DRAFTED,
        }:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not retryable")

        retried = job.model_copy(
            update={
                "status": SelfProgrammingStatus.QUEUED,
                "queue_status": SelfProgrammingStatus.QUEUED.value,
                "frozen_reason": None,
            }
        )
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": retried,
                    "current_thought": "已重新排队，等待委托执行。",
                }
            )
        )
        return {"success": True, "message": "已重试", "job_id": job_id}

    @router.post("/self-programming/{job_id}/thaw")
    def thaw_job(
        job_id: str,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.FROZEN:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not frozen")

        thawed = job.model_copy(
            update={
                "status": SelfProgrammingStatus.QUEUED,
                "queue_status": SelfProgrammingStatus.QUEUED.value,
                "frozen_reason": None,
            }
        )
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": thawed,
                    "current_thought": "冻结任务已解冻并重新入队。",
                }
            )
        )
        return {"success": True, "message": "已解冻", "job_id": job_id}

    @router.post("/self-programming/{job_id}/promote")
    def promote_job(
        job_id: str,
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status not in {SelfProgrammingStatus.APPLIED, SelfProgrammingStatus.VERIFYING}:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not promotable")

        promoted = job.model_copy(update={"promotion_status": "promoted"})
        state_store.set(
            state.model_copy(
                update={
                    "self_programming_job": promoted,
                    "current_thought": _compose_reflective_thought(
                        state.current_thought,
                        summary=f"{promoted.target_area} 的补丁已通过晋升门禁并生效",
                        next_step="我会盯一轮稳定性，确认这次提升不是偶然通过。",
                    ),
                }
            )
        )
        persona_service.infer_self_programming_emotion("applied", promoted.target_area)
        return {"success": True, "message": "已晋升", "job_id": job_id}

    @router.post("/self-programming/{job_id}/approve")
    def approve_job(
        job_id: str,
        request: ApprovalRequest | None = None,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.PENDING_APPROVAL:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not pending_approval")

        approved_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.VERIFYING,
                "approval_reason": request.reason if request else None,
            }
        )
        new_state = state.model_copy(
            update={
                "self_programming_job": approved_job,
                "current_thought": f"太好了，我的自我编程方案得到了批准，正在对 {job.target_area} 执行验证。",
            }
        )
        state_store.set(new_state)
        return {"success": True, "message": "已批准", "job_id": job_id}

    @router.post("/self-programming/{job_id}/reject")
    def reject_job(
        job_id: str,
        request: ApprovalRequest,
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail="Job not found or not current")
        if job.status != SelfProgrammingStatus.PENDING_APPROVAL:
            raise HTTPException(status_code=409, detail=f"Job status is {job.status.value}, not pending_approval")

        rejected_job = job.model_copy(
            update={
                "status": SelfProgrammingStatus.REJECTED,
                "approval_reason": request.reason or "用户拒绝",
                "rollback_info": f"被用户拒绝: {request.reason or '无原因'}",
                "rejection_phase": "promotion",
                "rejection_reason": request.reason or "用户拒绝",
                "rejected_by": "human",
                "rejected_at": datetime.now(timezone.utc),
            }
        )
        new_state = _finish_state_with_rejection(state, rejected_job)
        state_store.set(new_state)
        persona_service.infer_self_programming_emotion("rejected", rejected_job.target_area)
        return {"success": True, "message": "已拒绝", "job_id": job_id}

    @router.get("/self-programming/history")
    def get_self_programming_history(
        request: Request,
        limit: int = 50,
    ) -> dict:
        history = _get_history(request)
        entries = history.get_recent(limit)
        return {
            "entries": [
                {
                    "job_id": e.job_id,
                    "target_area": e.target_area,
                    "reason": e.reason,
                    "reason_statement": e.reason_statement,
                    "direction_statement": e.direction_statement,
                    "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                    "outcome": e.patch_summary or e.spec[:80],
                    "touched_files": list(e.touched_files),
                    "created_at": e.created_at,
                    "completed_at": e.completed_at or None,
                    "health_score": e.health_score,
                    "had_rollback": (e.status.value if hasattr(e.status, "value") else str(e.status)) == "rolled_back",
                    "rejection_phase": e.rejection_phase,
                    "rejection_reason": e.rejection_reason,
                    "start_approved_at": e.start_approved_at,
                    "approved_at": e.approved_at,
                }
                for e in entries
            ],
        }

    @router.post("/self-programming/{job_id}/rollback")
    def rollback_job_endpoint(
        job_id: str,
        http_request: Request,
        request: ApprovalRequest | None = None,
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found in current state")

        executor = _get_executor(http_request)
        if executor is None:
            raise HTTPException(status_code=503, detail="rollback executor is unavailable")

        try:
            rollback_result = executor.smart_rollback(
                job,
                reason=RollbackReason.MANUAL_REQUEST,
                reason_detail=request.reason if request and request.reason else "manual rollback",
            )
            if rollback_result is None:
                raise HTTPException(status_code=500, detail="回滚失败: 无可用快照")

            rollback_info = rollback_result.summary
            updated_job = job.model_copy(
                update={
                    "status": (
                        SelfProgrammingStatus.FAILED
                        if rollback_result.status in {RollbackStatus.SUCCESS, RollbackStatus.PARTIAL}
                        else job.status
                    ),
                    "rollback_info": rollback_info,
                }
            )
            new_state = state.model_copy(
                update={
                    "self_programming_job": updated_job,
                    "current_thought": _build_rollback_reflective_thought(
                        previous_thought=state.current_thought,
                        target_area=updated_job.target_area,
                        rollback_status=rollback_result.status,
                        rollback_info=rollback_info,
                    ),
                }
            )
            state_store.set(new_state)
            if updated_job.status == SelfProgrammingStatus.FAILED:
                persona_service.infer_self_programming_emotion("failed", updated_job.target_area)

            try:
                history = _get_history(http_request)
                history.record_from_job(
                    updated_job,
                    status=HistoryEntryStatus.ROLLED_BACK,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception:
                logger.debug("failed to persist rollback history", exc_info=True)

            return {
                "success": rollback_result.status in {RollbackStatus.SUCCESS, RollbackStatus.PARTIAL, RollbackStatus.SKIPPED},
                "message": rollback_info or "回滚完成",
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Rollback failed")
            raise HTTPException(status_code=500, detail=f"回滚失败: {exc}")

    return router


def _finish_state_with_rejection(state: BeingState, job) -> BeingState:
    reason = job.approval_reason or "未知"
    return state.model_copy(
        update={
            "focus_mode": FocusMode.AUTONOMY,
            "self_programming_job": job,
            "current_thought": _compose_reflective_thought(
                state.current_thought,
                summary=f"这次关于 {job.target_area} 的自我编程被拒绝了",
                next_step=f"我会先复盘拒绝点，再提交更小更稳的方案。原因：{reason}",
            ),
        }
    )


def _build_rollback_reflective_thought(
    previous_thought: str | None,
    target_area: str,
    rollback_status: RollbackStatus,
    rollback_info: str,
) -> str:
    rollback_summary = rollback_info.strip()[:100]
    if rollback_status in {RollbackStatus.SUCCESS, RollbackStatus.PARTIAL}:
        return _compose_reflective_thought(
            previous_thought,
            summary=f"{target_area} 的改动已回滚",
            next_step=f"我先稳住系统，再把失败点整理成可复现清单。回滚摘要：{rollback_summary}",
        )
    return _compose_reflective_thought(
        previous_thought,
        summary=f"{target_area} 的回滚没有完全生效",
        next_step=f"我需要继续排查恢复路径。回滚摘要：{rollback_summary}",
    )


def _compose_reflective_thought(previous_thought: str | None, *, summary: str, next_step: str) -> str:
    normalized_summary = summary.strip().rstrip("。")
    normalized_next_step = next_step.strip().rstrip("。")
    normalized_previous = (previous_thought or "").strip().rstrip("。")
    if not normalized_previous:
        return f"{normalized_summary}。{normalized_next_step}。"

    clipped_previous = normalized_previous if len(normalized_previous) <= 48 else f"{normalized_previous[:48]}…"
    return f"刚才我还在想「{clipped_previous}」。{normalized_summary}。{normalized_next_step}。"
