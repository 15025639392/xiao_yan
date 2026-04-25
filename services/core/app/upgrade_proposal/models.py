"""升级计划书存储层。

复用 StateStore 的持久化机制，将计划书保存在 BeingState.upgrade_proposals 中。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from app.domain.models import (
    BeingState,
    UpgradeProposal,
    UpgradeProposalCategory,
    UpgradeProposalPriority,
    UpgradeProposalStatus,
)
from app.runtime import StateStore


class UpgradeProposalStore:
    """管理小晏的升级计划书生命周期。

    所有操作都通过 StateStore 进行，确保线程安全和持久化。
    """

    MAX_HISTORY = 50  # 最多保留 50 条历史记录

    def __init__(self, state_store: StateStore) -> None:
        self._state_store = state_store

    def _get_state(self) -> BeingState:
        return self._state_store.get()

    def _save_state(self, state: BeingState) -> None:
        self._state_store.set(state)

    def list_all(self) -> list[UpgradeProposal]:
        """返回所有计划书（按时间倒序）。"""
        state = self._get_state()
        return list(reversed(state.upgrade_proposals))

    def list_pending(self) -> list[UpgradeProposal]:
        """返回待审批的计划书。"""
        return [
            p for p in self.list_all()
            if p.status == UpgradeProposalStatus.SUBMITTED
        ]

    def list_by_category(self, category: UpgradeProposalCategory) -> list[UpgradeProposal]:
        """按分类筛选。"""
        return [p for p in self.list_all() if p.category == category]

    def find_by_id(self, proposal_id: str) -> UpgradeProposal | None:
        """按 ID 查找。"""
        state = self._get_state()
        for p in state.upgrade_proposals:
            if p.proposal_id == proposal_id:
                return p
        return None

    def save(self, proposal: UpgradeProposal) -> UpgradeProposal:
        """保存或更新计划书。"""
        state = self._get_state()
        proposals = list(state.upgrade_proposals)

        # 查找并替换已有记录
        for i, existing in enumerate(proposals):
            if existing.proposal_id == proposal.proposal_id:
                proposals[i] = proposal
                break
        else:
            proposals.append(proposal)

        # 限制历史数量
        if len(proposals) > self.MAX_HISTORY:
            proposals = proposals[-self.MAX_HISTORY:]

        state.upgrade_proposals = proposals
        if proposal.status == UpgradeProposalStatus.SUBMITTED:
            state.last_upgrade_proposal_at = proposal.created_at

        self._save_state(state)
        return proposal

    def approve(self, proposal_id: str, approver: str) -> UpgradeProposal | None:
        """审批通过。"""
        proposal = self.find_by_id(proposal_id)
        if proposal is None:
            return None
        if proposal.status != UpgradeProposalStatus.SUBMITTED:
            return None

        updated = proposal.model_copy(update={
            "status": UpgradeProposalStatus.APPROVED,
            "approved_at": datetime.now(timezone.utc),
            "approved_by": approver,
        })
        self.save(updated)
        return updated

    def reject(self, proposal_id: str, approver: str, reason: str) -> UpgradeProposal | None:
        """审批驳回。"""
        proposal = self.find_by_id(proposal_id)
        if proposal is None:
            return None
        if proposal.status != UpgradeProposalStatus.SUBMITTED:
            return None

        updated = proposal.model_copy(update={
            "status": UpgradeProposalStatus.REJECTED,
            "rejected_at": datetime.now(timezone.utc),
            "rejected_by": approver,
            "reject_reason": reason,
        })
        self.save(updated)
        return updated

    def mark_implemented(self, proposal_id: str) -> UpgradeProposal | None:
        """标记为已实施。"""
        proposal = self.find_by_id(proposal_id)
        if proposal is None:
            return None
        if proposal.status != UpgradeProposalStatus.APPROVED:
            return None

        updated = proposal.model_copy(update={
            "status": UpgradeProposalStatus.IMPLEMENTED,
            "implemented_at": datetime.now(timezone.utc),
            "observation_result": "unknown",
        })
        self.save(updated)
        return updated

    def update_observation(
        self,
        proposal_id: str,
        result: Literal["success", "partial", "failed", "unknown"],
        notes: str | None = None,
    ) -> UpgradeProposal | None:
        """更新观察期结果。"""
        proposal = self.find_by_id(proposal_id)
        if proposal is None:
            return None

        updated = proposal.model_copy(update={
            "observation_result": result,
            "observation_notes": notes,
        })
        self.save(updated)
        return updated

    def get_recent_history(self, limit: int = 50) -> list[UpgradeProposal]:
        """获取最近历史（用于防重复检查）。"""
        state = self._get_state()
        return list(reversed(state.upgrade_proposals[-limit:]))

    def has_pending_in_domain(self, category: UpgradeProposalCategory, target_domain: str) -> bool:
        """检查同一领域是否有待处理的计划。"""
        for p in self.list_all():
            if p.category == category and p.target_domain == target_domain:
                if p.status in (UpgradeProposalStatus.SUBMITTED, UpgradeProposalStatus.APPROVED):
                    return True
        return False
