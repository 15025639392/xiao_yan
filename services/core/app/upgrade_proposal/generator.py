"""升级计划书生成器。

负责：
- 检测升级信号（瓶颈、失败、用户建议等）
- 自动分类（workflow_fix / habit_adjustment / new_capability / boundary_tuning）
- 防重复检查（语义重复、状态锁、冷却期）
- 构建完整的 UpgradeProposal
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal

from app.domain.models import (
    BeingState,
    UpgradeProposal,
    UpgradeProposalCategory,
    UpgradeProposalPriority,
    UpgradeProposalStatus,
    XhsWorkStatus,
)
from app.memory.models import MemoryEvent
from app.upgrade_proposal.models import UpgradeProposalStore


# ── 信号检测 ──────────────────────────────────────────────────────────────


def detect_upgrade_signal(
    state: BeingState,
    recent_events: list[MemoryEvent],
    now: datetime,
) -> tuple[bool, str, list[str], dict]:
    """检测是否需要生成升级计划书。

    返回: (should_upgrade, motivation, pain_points, observed_data)
    """
    pain_points: list[str] = []
    observed_data: dict = {}

    # 信号 1：小红书工作流反复失败
    xhs_signal, xhs_motivation, xhs_pains, xhs_data = _detect_xhs_blocked_signal(state, now)
    if xhs_signal:
        return True, xhs_motivation, xhs_pains, xhs_data

    # 信号 2：用户明确给出改进建议
    user_signal, user_motivation, user_pains, user_data = _detect_user_suggestion_signal(recent_events)
    if user_signal:
        return True, user_motivation, user_pains, user_data

    # 信号 3：能量长期低迷 + 有 active focus（倦怠信号）
    burnout_signal, burnout_motivation, burnout_pains, burnout_data = _detect_burnout_signal(state, recent_events, now)
    if burnout_signal:
        return True, burnout_motivation, burnout_pains, burnout_data

    # 信号 4：inner memory 中反复出现同一类问题
    recurring_signal, recurring_motivation, recurring_pains, recurring_data = _detect_recurring_issue_signal(recent_events)
    if recurring_signal:
        return True, recurring_motivation, recurring_pains, recurring_data

    return False, "", [], {}


def _detect_xhs_blocked_signal(state: BeingState, now: datetime) -> tuple[bool, str, list[str], dict]:
    """检测小红书连续阻塞信号。"""
    domain = state.xhs_work_domain
    if domain is None:
        return False, "", [], {}

    if domain.state.status != XhsWorkStatus.BLOCKED:
        return False, "", [], {}

    # 检查 blocked 历史（从 upgrade_proposals 和当前状态推断）
    blocked_reason = domain.state.blocked_reason or "未知原因"
    blocked_at = domain.state.blocked_at
    blocked_duration = 0
    if blocked_at:
        blocked_duration = (now - blocked_at).total_seconds()

    # 简单规则：当前处于 BLOCKED 状态即视为信号
    # 更复杂的规则可以统计最近 N 次 tick 的 blocked 次数
    pain_points = [f"小红书发布阻塞：{blocked_reason}"]
    if blocked_duration > 300:
        pain_points.append(f"已阻塞 {int(blocked_duration)} 秒")

    observed_data = {
        "domain": "xiaohongshu",
        "blocked_reason": blocked_reason,
        "blocked_at": blocked_at.isoformat() if blocked_at else None,
        "blocked_duration_seconds": blocked_duration,
    }

    return True, f"小红书工作流遇到阻塞：{blocked_reason}", pain_points, observed_data


def _detect_user_suggestion_signal(recent_events: list[MemoryEvent]) -> tuple[bool, str, list[str], dict]:
    """从用户对话中提取改进建议。"""
    suggestion_keywords = [
        "你应该", "你可以", "建议你", "试试", "改一下", "优化",
        "能不能", "可以改成", "最好", "建议",
    ]

    for event in reversed(recent_events):
        if event.kind != "chat" or event.role != "user":
            continue
        content = event.content or ""
        for keyword in suggestion_keywords:
            if keyword in content:
                return True, f"用户建议：{content[:50]}...", [content], {"source_event_id": event.entry_id}

    return False, "", [], {}


def _detect_burnout_signal(
    state: BeingState,
    recent_events: list[MemoryEvent],
    now: datetime,
) -> tuple[bool, str, list[str], dict]:
    """检测倦怠信号：长期低能量 + 有未完成的 focus。"""
    # 需要 world_state 信息，但这里只基于 state 和 events 推断
    # 简化：检查最近是否有大量 inner memory 表达疲惫
    tired_count = 0
    for event in recent_events:
        if event.kind == "inner" and event.content and ("困" in event.content or "累" in event.content):
            tired_count += 1

    if tired_count >= 3 and state.focus_subject is not None:
        return (
            True,
            "最近状态不太好，inner memory 中多次表达疲惫",
            ["多次记录到疲惫状态", "仍有未完成的 focus"],
            {"tired_inner_count": tired_count},
        )

    return False, "", [], {}


def _detect_recurring_issue_signal(recent_events: list[MemoryEvent]) -> tuple[bool, str, list[str], dict]:
    """检测 inner memory 中反复出现的同一类问题。"""
    # 简化实现：检查最近 20 条 inner memory 中是否有重复关键词
    inner_contents = [e.content for e in recent_events if e.kind == "inner" and e.content]
    if len(inner_contents) < 5:
        return False, "", [], {}

    # 提取关键词（简单分词）
    from collections import Counter
    words = []
    for content in inner_contents:
        words.extend(content.split("，"))
        words.extend(content.split("。"))

    # 统计重复短语
    counter = Counter(w.strip() for w in words if len(w.strip()) >= 4)
    most_common = counter.most_common(1)
    if most_common and most_common[0][1] >= 3:
        phrase, count = most_common[0]
        return (
            True,
            f"inner memory 中反复提到'{phrase}'（{count}次）",
            [f"反复遇到：{phrase}"],
            {"recurring_phrase": phrase, "count": count},
        )

    return False, "", [], {}


# ── 分类 ──────────────────────────────────────────────────────────────────


def classify_upgrade_proposal(
    motivation: str,
    pain_points: list[str],
    observed_data: dict,
) -> tuple[UpgradeProposalCategory, str]:
    """根据信号自动分类。

    返回: (category, target_domain)
    """
    text = (motivation + " " + " ".join(pain_points)).lower()

    # 边界调整
    if any(word in text for word in ["权限", "审批", "放宽", "收紧", "安全", "限制"]):
        return UpgradeProposalCategory.BOUNDARY_TUNING, _infer_target_domain_from_text(text, observed_data)

    # 新能力
    if any(word in text for word in ["想学", "试试", "新平台", "新工具", "接入", "扩展"]):
        return UpgradeProposalCategory.NEW_CAPABILITY, _infer_target_domain_from_text(text, observed_data)

    # 流程修复（阻塞、失败、报错）
    if any(word in text for word in ["卡住", "失败", "阻塞", "报错", "不行", "错误", "异常"]):
        return UpgradeProposalCategory.WORKFLOW_FIX, _infer_target_domain_from_text(text, observed_data)

    # 习惯调整（节奏、效率、频率）
    if any(word in text for word in ["节奏", "效率", "太慢", "太频繁", "间隔", "时间", "习惯"]):
        return UpgradeProposalCategory.HABIT_ADJUSTMENT, _infer_target_domain_from_text(text, observed_data)

    # 兜底：根据 observed_data 推断
    domain = observed_data.get("domain", "")
    if domain:
        return UpgradeProposalCategory.HABIT_ADJUSTMENT, domain

    return UpgradeProposalCategory.HABIT_ADJUSTMENT, "general"


def _infer_target_domain_from_text(text: str, observed_data: dict) -> str:
    """从文本和数据中推断目标领域。"""
    if observed_data.get("domain"):
        return observed_data["domain"]

    if "小红书" in text or "xiaohongshu" in text:
        return "xiaohongshu"
    if "聊天" in text or "对话" in text:
        return "chat"
    if "记忆" in text:
        return "memory"
    if "浏览器" in text or "browser" in text:
        return "browser"

    return "general"


# ── 优先级 ────────────────────────────────────────────────────────────────


def infer_priority(
    category: UpgradeProposalCategory,
    pain_points: list[str],
    observed_data: dict,
) -> UpgradeProposalPriority:
    """根据分类和上下文推断优先级。"""
    if category == UpgradeProposalCategory.WORKFLOW_FIX:
        blocked_duration = observed_data.get("blocked_duration_seconds", 0)
        if blocked_duration > 900:  # 15 分钟
            return UpgradeProposalPriority.CRITICAL
        if blocked_duration > 300:  # 5 分钟
            return UpgradeProposalPriority.HIGH
        return UpgradeProposalPriority.MEDIUM

    if category == UpgradeProposalCategory.BOUNDARY_TUNING:
        # 安全相关默认 medium，涉及放宽必须人工审核
        return UpgradeProposalPriority.MEDIUM

    if category == UpgradeProposalCategory.NEW_CAPABILITY:
        domain = observed_data.get("domain", "")
        if domain == "xiaohongshu":
            return UpgradeProposalPriority.HIGH
        return UpgradeProposalPriority.MEDIUM

    # habit_adjustment 默认 low
    return UpgradeProposalPriority.LOW


# ── 防重复 ────────────────────────────────────────────────────────────────


def _compute_fingerprint(category: UpgradeProposalCategory, target_domain: str, pain_points: list[str]) -> str:
    """计算内容指纹。"""
    raw = f"{category.value}:{target_domain}:{','.join(sorted(pain_points))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def is_semantically_duplicate(
    category: UpgradeProposalCategory,
    target_domain: str,
    pain_points: list[str],
    history: list[UpgradeProposal],
) -> tuple[bool, str]:
    """检查是否存在语义重复的计划书。"""
    for plan in history:
        if plan.category != category:
            continue
        if plan.target_domain != target_domain:
            continue

        # pain_points 有重叠
        existing_pains = set(plan.pain_points)
        new_pains = set(pain_points)
        if existing_pains & new_pains:
            return True, f"已有同类计划 #{plan.proposal_id} 处理相同问题，状态：{plan.status.value}"

    return False, ""


def is_domain_locked(
    category: UpgradeProposalCategory,
    target_domain: str,
    store: UpgradeProposalStore,
) -> bool:
    """检查同一领域是否有待处理的计划。"""
    return store.has_pending_in_domain(category, target_domain)


def cooldown_for_implemented_plan(
    plan: UpgradeProposal,
    now: datetime,
) -> tuple[bool, timedelta]:
    """检查实施后冷却期是否已过。

    返回: (冷却中, 剩余时间)
    """
    if plan.status != UpgradeProposalStatus.IMPLEMENTED:
        return False, timedelta(0)

    if plan.implemented_at is None:
        return False, timedelta(0)

    result = plan.observation_result or "unknown"
    if result == "success":
        cooldown = timedelta(days=30)
    elif result == "partial":
        cooldown = timedelta(days=14)
    elif result == "failed":
        cooldown = timedelta(days=7)
    else:
        cooldown = timedelta(days=14)

    elapsed = now - plan.implemented_at
    if elapsed < cooldown:
        return True, cooldown - elapsed

    return False, timedelta(0)


def check_all_duplicate_gates(
    category: UpgradeProposalCategory,
    target_domain: str,
    pain_points: list[str],
    store: UpgradeProposalStore,
    now: datetime,
) -> tuple[bool, str]:
    """完整的防重复检查。

    返回: (是否允许生成, 阻止原因)
    """
    history = store.get_recent_history(limit=50)

    # 第一层：语义重复
    is_dup, dup_reason = is_semantically_duplicate(category, target_domain, pain_points, history)
    if is_dup:
        return False, f"语义重复：{dup_reason}"

    # 第二层：状态锁
    if is_domain_locked(category, target_domain, store):
        return False, "该领域已有待处理计划，等待完成后再提"

    # 第三层：实施后冷却期
    for plan in history:
        if plan.category == category and plan.target_domain == target_domain:
            in_cooldown, remaining = cooldown_for_implemented_plan(plan, now)
            if in_cooldown:
                return False, f"冷却期中，{remaining.days}天后可再提同类计划"

    # 第四层：全局冷却期（24 小时内最多 1 个）
    state = store._get_state()
    if state.last_upgrade_proposal_at:
        global_cooldown = timedelta(hours=24)
        elapsed = now - state.last_upgrade_proposal_at
        if elapsed < global_cooldown:
            remaining = global_cooldown - elapsed
            return False, f"全局冷却中，{remaining.total_seconds() // 3600}小时后可再提"

    return True, ""


# ── 构建计划书 ────────────────────────────────────────────────────────────


def build_upgrade_proposal(
    motivation: str,
    pain_points: list[str],
    observed_data: dict,
    store: UpgradeProposalStore,
    now: datetime,
) -> UpgradeProposal | None:
    """构建完整的升级计划书。

    如果防重复检查不通过，返回 None。
    """
    category, target_domain = classify_upgrade_proposal(motivation, pain_points, observed_data)
    priority = infer_priority(category, pain_points, observed_data)

    # 防重复检查
    allowed, reason = check_all_duplicate_gates(category, target_domain, pain_points, store, now)
    if not allowed:
        return None

    fingerprint = _compute_fingerprint(category, target_domain, pain_points)

    # 生成 her_voice（自然语言表达）
    her_voice = _build_her_voice(motivation, pain_points, category)

    proposal_id = f"upg-{now.strftime('%Y%m%d%H%M%S')}-{fingerprint[:8]}"

    return UpgradeProposal(
        proposal_id=proposal_id,
        created_at=now,
        status=UpgradeProposalStatus.SUBMITTED,
        her_voice=her_voice,
        motivation=motivation,
        pain_points=pain_points,
        observed_data=observed_data,
        category=category,
        target_domain=target_domain,
        suggested_priority=priority,
        content_fingerprint=fingerprint,
    )


def _build_her_voice(
    motivation: str,
    pain_points: list[str],
    category: UpgradeProposalCategory,
) -> str:
    """根据分类和信号生成她的人格化表达。"""
    if category == UpgradeProposalCategory.WORKFLOW_FIX:
        return f"我觉得{motivation}，{pain_points[0] if pain_points else '想调整一下流程'}。"

    if category == UpgradeProposalCategory.HABIT_ADJUSTMENT:
        return f"{motivation}，这个节奏可能需要调整一下。"

    if category == UpgradeProposalCategory.NEW_CAPABILITY:
        return f"{motivation}，想试试能不能学会这个新东西。"

    if category == UpgradeProposalCategory.BOUNDARY_TUNING:
        return f"{motivation}，想调整一下现在的限制。"

    return motivation
