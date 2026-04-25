"""自我升级计划书系统。

小晏通过自然语言表达升级意愿，系统在背后自动分类、防重复、管理审批流。
她不"自我编程"，而是"提出想法"——执行由人完成，经历由她记忆。
"""

from app.upgrade_proposal.models import UpgradeProposalStore
from app.upgrade_proposal.generator import (
    detect_upgrade_signal,
    classify_upgrade_proposal,
    build_upgrade_proposal,
    is_semantically_duplicate,
    is_domain_locked,
    cooldown_for_implemented_plan,
)
from app.upgrade_proposal.helpers import (
    build_upgrade_proposal_thought,
    build_upgrade_wait_thought,
    build_upgrade_approved_thought,
    build_upgrade_rejected_thought,
    build_upgrade_implemented_thought,
)

__all__ = [
    "UpgradeProposalStore",
    "detect_upgrade_signal",
    "classify_upgrade_proposal",
    "build_upgrade_proposal",
    "is_semantically_duplicate",
    "is_domain_locked",
    "cooldown_for_implemented_plan",
    "build_upgrade_proposal_thought",
    "build_upgrade_wait_thought",
    "build_upgrade_approved_thought",
    "build_upgrade_rejected_thought",
    "build_upgrade_implemented_thought",
]
