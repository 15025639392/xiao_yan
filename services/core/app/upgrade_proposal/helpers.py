"""升级计划书相关的人格化表达生成器。

生成 inner memory / autobio memory 的文本内容，
保持小晏的自我叙事连续性。
"""

from __future__ import annotations

from datetime import datetime

from app.domain.models import UpgradeProposal, UpgradeProposalStatus


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


# ── 计划书生成时的表达 ────────────────────────────────────────────────────


def build_upgrade_proposal_thought(
    proposal: UpgradeProposal,
    now: datetime,
    world_state,
) -> str:
    """生成计划书时的内心想法（inner memory）。"""
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)

    category_labels = {
        "workflow_fix": "流程",
        "habit_adjustment": "习惯",
        "new_capability": "新能力",
        "boundary_tuning": "边界",
    }
    label = category_labels.get(proposal.category.value, "调整")

    return (
        f"{prefix}{tone}我觉得{proposal.motivation}，"
        f"想提一个{label}方面的升级计划。"
    )


# ── 等待审批时的表达 ──────────────────────────────────────────────────────


def build_upgrade_wait_thought(
    proposal: UpgradeProposal,
    now: datetime,
    world_state,
) -> str:
    """等待审批时的内心想法。"""
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)

    return (
        f"{prefix}{tone}我还在等我的升级计划（{proposal.proposal_id}）被审阅，"
        f"有点期待又有点紧张。"
    )


# ── 审批通过时的表达 ──────────────────────────────────────────────────────


def build_upgrade_approved_thought(
    proposal: UpgradeProposal,
    now: datetime,
    world_state,
) -> str:
    """审批通过时的内心想法（autobio memory）。"""
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)

    return (
        f"{prefix}{tone}我的升级计划终于被通过了（{proposal.proposal_id}），"
        f"关于{proposal.target_domain}的{proposal.category.value}调整，"
        f"接下来应该能更顺畅一些。"
    )


# ── 审批驳回时的表达 ──────────────────────────────────────────────────────


def build_upgrade_rejected_thought(
    proposal: UpgradeProposal,
    now: datetime,
    world_state,
) -> str:
    """审批驳回时的内心想法（inner memory）。"""
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)

    reason = proposal.reject_reason or "没有说明具体原因"
    return (
        f"{prefix}{tone}我的升级计划（{proposal.proposal_id}）被退回来了，"
        f"理由是：{reason}。我再想想别的办法。"
    )


# ── 实施完成时的表达 ──────────────────────────────────────────────────────


def build_upgrade_implemented_thought(
    proposal: UpgradeProposal,
    now: datetime,
    world_state,
) -> str:
    """实施完成后的自传体记忆。"""
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)

    benefit = proposal.expected_benefit or "感觉顺畅了一些"
    return (
        f"{prefix}{tone}我的'{proposal.her_voice[:30]}...'这个计划被实施了。"
        f"现在{benefit}。"
    )


# ── 被阻止生成时的替代表达 ────────────────────────────────────────────────


def build_deferred_upgrade_thought(
    category: str,
    target_domain: str,
    reason: str,
    now: datetime,
    world_state,
) -> str:
    """计划书被防重复机制阻止时的替代 inner memory。"""
    prefix = _time_prefix(now)
    tone = _world_tone(world_state)

    if "语义重复" in reason:
        return (
            f"{prefix}{tone}关于{target_domain}的问题我之前已经提过升级计划了，"
            f"暂时先不重复提。"
        )

    if "状态锁" in reason or "待处理" in reason:
        return (
            f"{prefix}{tone}关于{target_domain}我已经有一个想法在排队了，"
            f"先集中精力把那一个做完。"
        )

    if "冷却期" in reason:
        return (
            f"{prefix}{tone}上次改的效果还在观察中，"
            f"过段时间再看看要不要进一步调整{target_domain}。"
        )

    if "全局冷却" in reason:
        return (
            f"{prefix}{tone}刚提过一个计划不久，"
            f"先等等看之前的反馈，不急着再提新的。"
        )

    return f"{prefix}{tone}关于{target_domain}的升级想法暂时先放一放，{reason}。"
