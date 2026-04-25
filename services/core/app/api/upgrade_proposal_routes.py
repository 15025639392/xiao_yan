"""升级计划书 API 路由。

提供计划书的查询、审批、状态更新接口。
复用 capability 审批的 UI 模式。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_state_store
from app.domain.models import (
    UpgradeProposal,
    UpgradeProposalCategory,
    UpgradeProposalPriority,
    UpgradeProposalStatus,
)
from app.runtime import StateStore
from app.upgrade_proposal.models import UpgradeProposalStore


# ── 请求/响应模型 ─────────────────────────────────────────────────────────


class UpgradeProposalListResponse(BaseModel):
    proposals: list[UpgradeProposal]
    total: int


class UpgradeProposalApprovalRequest(BaseModel):
    approver: str = "admin"


class UpgradeProposalRejectionRequest(BaseModel):
    approver: str = "admin"
    reason: str


class UpgradeProposalObservationRequest(BaseModel):
    result: Literal["success", "partial", "failed", "unknown"]
    notes: str | None = None


class UpgradeProposalActionResponse(BaseModel):
    ok: bool
    proposal: UpgradeProposal | None = None
    message: str | None = None


# ── 路由构建 ──────────────────────────────────────────────────────────────


def build_upgrade_proposal_router() -> APIRouter:
    router = APIRouter()

    def _get_store(state_store: StateStore = Depends(get_state_store)) -> UpgradeProposalStore:
        return UpgradeProposalStore(state_store)

    @router.get("/upgrade-proposals")
    def list_upgrade_proposals(
        status: UpgradeProposalStatus | None = Query(default=None),
        category: UpgradeProposalCategory | None = Query(default=None),
        target_domain: str | None = Query(default=None),
        limit: int = Query(default=30, ge=1, le=200),
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> UpgradeProposalListResponse:
        all_proposals = store.list_all()
        filtered = all_proposals

        if status is not None:
            filtered = [p for p in filtered if p.status == status]
        if category is not None:
            filtered = [p for p in filtered if p.category == category]
        if target_domain is not None:
            filtered = [p for p in filtered if p.target_domain == target_domain]

        return UpgradeProposalListResponse(
            proposals=filtered[:limit],
            total=len(filtered),
        )

    @router.get("/upgrade-proposals/{proposal_id}")
    def get_upgrade_proposal(
        proposal_id: str,
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> UpgradeProposal | None:
        return store.find_by_id(proposal_id)

    @router.post("/upgrade-proposals/{proposal_id}/approve")
    def approve_upgrade_proposal(
        proposal_id: str,
        request: UpgradeProposalApprovalRequest,
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> UpgradeProposalActionResponse:
        proposal = store.approve(proposal_id, request.approver)
        if proposal is None:
            return UpgradeProposalActionResponse(
                ok=False, proposal=None, message="计划书不存在或状态不允许审批"
            )
        return UpgradeProposalActionResponse(ok=True, proposal=proposal)

    @router.post("/upgrade-proposals/{proposal_id}/reject")
    def reject_upgrade_proposal(
        proposal_id: str,
        request: UpgradeProposalRejectionRequest,
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> UpgradeProposalActionResponse:
        proposal = store.reject(proposal_id, request.approver, request.reason)
        if proposal is None:
            return UpgradeProposalActionResponse(
                ok=False, proposal=None, message="计划书不存在或状态不允许驳回"
            )
        return UpgradeProposalActionResponse(ok=True, proposal=proposal)

    @router.post("/upgrade-proposals/{proposal_id}/implement")
    def mark_upgrade_proposal_implemented(
        proposal_id: str,
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> UpgradeProposalActionResponse:
        proposal = store.mark_implemented(proposal_id)
        if proposal is None:
            return UpgradeProposalActionResponse(
                ok=False, proposal=None, message="计划书不存在或状态不允许标记实施"
            )
        return UpgradeProposalActionResponse(ok=True, proposal=proposal)

    @router.post("/upgrade-proposals/{proposal_id}/observe")
    def update_upgrade_proposal_observation(
        proposal_id: str,
        request: UpgradeProposalObservationRequest,
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> UpgradeProposalActionResponse:
        proposal = store.update_observation(proposal_id, request.result, request.notes)
        if proposal is None:
            return UpgradeProposalActionResponse(
                ok=False, proposal=None, message="计划书不存在"
            )
        return UpgradeProposalActionResponse(ok=True, proposal=proposal)

    @router.get("/upgrade-proposals/stats/overview")
    def get_upgrade_proposal_stats(
        store: UpgradeProposalStore = Depends(_get_store),
    ) -> dict:
        all_proposals = store.list_all()
        status_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}

        for p in all_proposals:
            status_counts[p.status.value] = status_counts.get(p.status.value, 0) + 1
            category_counts[p.category.value] = category_counts.get(p.category.value, 0) + 1

        return {
            "total": len(all_proposals),
            "by_status": status_counts,
            "by_category": category_counts,
            "pending_count": len(store.list_pending()),
        }

    return router
