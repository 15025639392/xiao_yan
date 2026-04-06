from __future__ import annotations

from logging import getLogger
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_state_store
from app.domain.models import BeingState, FocusMode, SelfProgrammingStatus
from app.runtime import StateStore

logger = getLogger(__name__)


class ApprovalRequest(BaseModel):
    reason: str | None = None


def build_self_programming_router() -> APIRouter:
    router = APIRouter()

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
                "current_thought_override": "用户已批准，开始执行验证...",
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
            }
        )
        new_state = _finish_state_with_rejection(state, rejected_job)
        state_store.set(new_state)
        return {"success": True, "message": "已拒绝", "job_id": job_id}

    def _get_history() -> Any:
        from app.self_programming.history_store import SelfProgrammingHistory

        if not hasattr(_get_history, "_instance"):
            _get_history._instance = SelfProgrammingHistory(in_memory=True)
        return _get_history._instance

    @router.get("/self-programming/history")
    def get_self_programming_history(limit: int = 50) -> dict:
        history = _get_history()
        entries = history.get_recent(limit)
        return {
            "entries": [
                {
                    "job_id": e.job_id,
                    "target_area": e.target_area,
                    "reason": e.reason,
                    "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                    "outcome": e.patch_summary or e.spec[:80],
                    "touched_files": list(e.touched_files),
                    "created_at": e.created_at,
                    "completed_at": e.completed_at or None,
                    "health_score": None,
                    "had_rollback": (e.status.value if hasattr(e.status, "value") else str(e.status)) == "rolled_back",
                }
                for e in entries
            ],
        }

    @router.post("/self-programming/{job_id}/rollback")
    def rollback_job_endpoint(
        job_id: str,
        request: ApprovalRequest | None = None,
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        from app.self_programming.executor import SelfProgrammingExecutor

        state = state_store.get()
        job = state.self_programming_job
        if job is None or job.id != job_id:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found in current state")

        try:
            executor = SelfProgrammingExecutor()
            result = executor.rollback(job, reason=request.reason if request else None)
            rollback_info = getattr(result, "rollback_info", "") or ""
            new_state = state.model_copy(
                update={
                    "self_programming_job": result,
                    "current_thought": f"自我编程 {job_id} 已回滚: {rollback_info[:100]}",
                }
            )
            state_store.set(new_state)
            return {"success": True, "message": rollback_info or "回滚成功"}
        except Exception as exc:
            logger.exception("Rollback failed")
            raise HTTPException(status_code=500, detail=f"回滚失败: {exc}")

    return router


def _finish_state_with_rejection(state: BeingState, job) -> BeingState:
    return state.model_copy(
        update={
            "focus_mode": FocusMode.AUTONOMY,
            "self_programming_job": job,
            "current_thought": (
                f"这次关于 {job.target_area} 的自我编程被拒绝了。"
                f"原因：{job.approval_reason or '未知'}。"
                "我会记住这次的教训，下次做得更好。"
            ),
        }
    )

