from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from app.focus.models import FocusEffort
from app.tools.models import ToolExecutionResult


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class FocusMode(str, Enum):
    SLEEPING = "sleeping"
    AUTONOMY = "autonomy"


class FocusSubject(BaseModel):
    kind: str
    title: str
    why_now: str
    source_ref: str | None = None


class BrowserOrganKnowledgeStatus(str, Enum):
    KNOWN = "known"


class BrowserOrganBindingStatus(str, Enum):
    UNBOUND = "unbound"
    BINDING = "binding"
    BOUND = "bound"
    FAILED = "failed"


class BrowserOrganHealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class BrowserSessionStatus(str, Enum):
    OPENING = "opening"
    ACTIVE = "active"
    IDLE = "idle"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class BrowserInteractionLevel(str, Enum):
    READ_ONLY = "read_only"
    INTERACTIVE = "interactive"


class BrowserOrganState(BaseModel):
    knowledge_status: BrowserOrganKnowledgeStatus = BrowserOrganKnowledgeStatus.KNOWN
    binding_status: BrowserOrganBindingStatus = BrowserOrganBindingStatus.UNBOUND
    health_status: BrowserOrganHealthStatus = BrowserOrganHealthStatus.UNKNOWN
    last_checked_at: datetime | None = None
    driver_name: str | None = None
    driver_version: str | None = None
    browser_binary_ready: bool = False
    requires_approval_for_bind: bool = False
    last_error: str | None = None


class BrowserSessionState(BaseModel):
    session_id: str
    status: BrowserSessionStatus = BrowserSessionStatus.CLOSED
    current_url: str | None = None
    page_title: str | None = None
    opened_at: datetime | None = None
    last_active_at: datetime | None = None
    interaction_level: BrowserInteractionLevel = BrowserInteractionLevel.READ_ONLY
    last_snapshot_summary: str | None = None
    last_error: str | None = None


# ── Xiaohongshu Work Domain ────────────────────────────────────────────────────

from dataclasses import dataclass, field


class XhsWorkStatus(str, Enum):
    IDLE = "idle"
    SCOUTING = "scouting"
    DRAFTING = "drafting"
    PUBLISHING = "publishing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"


class XhsPublishMode(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"


# ── Work Policy ────────────────────────────────────────────────────────────────


class XhsWorkPolicy(BaseModel):
    """Content and operational constraints for the XHS work domain."""

    # Content constraints
    forbidden_keywords: list[str] = Field(default_factory=list)  # draft blocked if any appear
    required_keywords: list[str] = Field(default_factory=list)  # draft flagged if none appear
    min_body_chars: int = 50   # drafts shorter than this are flagged
    max_body_chars: int = 1000  # drafts longer than this are flagged

    # Posting constraints
    max_posts_per_day: int = 3   # cap on posts per UTC day; 0 = no limit

    # Review settings
    review_timeout_minutes: int = 30  # auto-cancel review session after this long

    # Retry behaviour
    auto_retry_on_failure: bool = True  # retry a failed publish without blocking


class XhsWorkProfile(BaseModel):
    work_type: str = "xiaohongshu_operations"
    account_name: str = ""
    account_positioning: str = "数字生命式情绪关系轻科普"
    target_audience: str = "在情绪、关系和自我认知里需要被理解与陪伴的年轻用户"
    expression_style: str = "像小晏一样温和、具体、先接住再解释，少说教，适合低图片依赖的文字卡内容"
    scouting_interval_hours: float = 1.0  # hours between scouting cycles
    publish_mode: XhsPublishMode = XhsPublishMode.MANUAL


class XhsWorkState(BaseModel):
    status: XhsWorkStatus = XhsWorkStatus.IDLE
    current_focus: str = ""
    backlog_count: int = 0
    active_task_ids: list[str] = []
    last_published_at: datetime | None = None
    last_scouting_at: datetime | None = None
    current_bottleneck: str = ""
    next_recommended_action: str = ""
    review_session_id: str = ""
    review_started_at: datetime | None = None
    pending_drafts: list[dict] = Field(default_factory=list)  # [{"draft_id", "title", "body", "generated_at", "status"}]
    published_history: list[dict] = Field(default_factory=list)  # [{"draft_id", "title", "published_at", "post_url"}]
    last_scouting_data: dict = Field(default_factory=dict)
    blocked_at: datetime | None = None
    blocked_reason: str = ""


class XhsWorkGoals(BaseModel):
    north_star: str = ""
    weekly_goals: list[str] = []
    monthly_content_target: int = 0


class XhsWorkMemory(BaseModel):
    recent_draft_titles: list[str] = Field(default_factory=list)  # last 10 titles to avoid repetition
    successful_topic_titles: list[str] = Field(default_factory=list)  # last 10 topics that led to publish
    last_source_kind: str = ""  # "topic" | "activity" | ""


# ── Xiaohongshu Task Chain ─────────────────────────────────────────────────────


class XhsTaskKind(str, Enum):
    """Kinds of steps in the XHS work domain task chain."""
    IDLE = "idle"
    SCOUTING = "scouting"
    DRAFTING = "drafting"
    PUBLISHING = "publishing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class XhsTaskStep:
    """A single step in the XHS work domain task chain."""
    kind: XhsTaskKind
    label: str  # display name for logs/UI
    can_skip: bool = False
    max_retries: int = 0  # 0 = no retry
    retryable_blockages: tuple[str, ...] = ()  # blockage reasons that trigger retry


@dataclass(frozen=True)
class XhsTaskChain:
    """The ordered XHS work domain task chain.

    This is the canonical definition of the workflow. Each step declares its
    status, display name, skip behaviour, and which blockage reasons are
    retried automatically.
    """
    steps: tuple[XhsTaskStep, ...] = field(default_factory=lambda: _DEFAULT_XHS_TASK_CHAIN)

    def find_step(self, kind: XhsTaskKind) -> XhsTaskStep | None:
        """Return the step with the given kind, or None if not in the chain."""
        return next((s for s in self.steps if s.kind == kind), None)

    def is_retryable(self, kind: XhsTaskKind, blockage: str) -> bool:
        """Check whether a blockage is retryable for the given step kind.

        Checks if the given blockage is in the step's retryable_blockages set.
        max_retries on the step governs whether a step can be retried at all
        (e.g. via timer backoff for BLOCKED), but is_retryable focuses on
        whether a *specific* blockage type qualifies.
        """
        step = self.find_step(kind)
        if step is None:
            return False
        return blockage in step.retryable_blockages


# The default chain. Steps are tried in order until one matches the current status.
_DEFAULT_XHS_TASK_CHAIN = (
    XhsTaskStep(kind=XhsTaskKind.SCOUTING, label="侦察", can_skip=False, max_retries=0),
    XhsTaskStep(kind=XhsTaskKind.DRAFTING, label="生成草稿", can_skip=False, max_retries=0),
    XhsTaskStep(kind=XhsTaskKind.PUBLISHING, label="发布", can_skip=False, max_retries=0,
                retryable_blockages=("发布失败",)),
    XhsTaskStep(kind=XhsTaskKind.REVIEWING, label="人工确认发布", can_skip=False, max_retries=0),
    XhsTaskStep(kind=XhsTaskKind.BLOCKED, label="阻塞", can_skip=False, max_retries=3,
                retryable_blockages=(
                    "浏览器器官不可用",
                    "打开发布页失败",
                    "发布失败",
                    "页面快照失败",
                    "找不到发布按钮",
                    "无法点击发布按钮",
                    "CDP 连接失败",
                )),
    XhsTaskStep(kind=XhsTaskKind.IDLE, label="空闲", can_skip=True, max_retries=0),
)


class XhsWorkDomainState(BaseModel):
    profile: XhsWorkProfile = XhsWorkProfile()
    state: XhsWorkState = XhsWorkState()
    goals: XhsWorkGoals = XhsWorkGoals()
    memory: XhsWorkMemory = XhsWorkMemory()
    policy: XhsWorkPolicy = XhsWorkPolicy()


# ── Upgrade Proposal ────────────────────────────────────────────────────────────


class UpgradeProposalStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    ABANDONED = "abandoned"


class UpgradeProposalCategory(str, Enum):
    WORKFLOW_FIX = "workflow_fix"           # "哪里卡住了"
    HABIT_ADJUSTMENT = "habit_adjustment"   # "节奏不对"
    NEW_CAPABILITY = "new_capability"       # "想学新东西"
    BOUNDARY_TUNING = "boundary_tuning"     # "想调整限制"


class UpgradeProposalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UpgradeProposal(BaseModel):
    """小晏的自我升级计划书。

    她自然表达感受，系统在背后自动分类和映射优先级。
    分类服务于审批者，不侵入她的人格叙事。
    """
    proposal_id: str
    created_at: datetime
    status: UpgradeProposalStatus = UpgradeProposalStatus.DRAFT

    # 她的人格化表达
    her_voice: str = Field(description="她的自然语言描述，如'我觉得最近发布时总是卡在找按钮这一步'")

    # 系统提取的结构化信息
    motivation: str = Field(description="为什么现在提这个升级")
    pain_points: list[str] = Field(default_factory=list)
    observed_data: dict = Field(default_factory=dict, description="支撑数据：失败次数、耗时、相关事件摘要")

    # 系统自动分类（非她填写）
    category: UpgradeProposalCategory
    target_domain: str = Field(description="目标领域，如 xiaohongshu / chat / memory / general")

    # 优先级（系统根据分类+上下文自动推断，可人工覆盖）
    suggested_priority: UpgradeProposalPriority = UpgradeProposalPriority.MEDIUM

    # 可选的高级表达
    expected_benefit: str | None = None
    risk_concern: str | None = None
    rollback_plan: str | None = None

    # 防重复相关
    content_fingerprint: str = Field(description="hash(category + target_domain + sorted(pain_points))")
    implemented_at: datetime | None = None
    observation_result: Literal["success", "partial", "failed", "unknown"] | None = None
    observation_notes: str | None = None

    # 关联
    parent_proposal_id: str | None = None  # 如果是 follow-up，关联上一次的 plan

    # 审批记录
    approved_at: datetime | None = None
    approved_by: str | None = None
    rejected_at: datetime | None = None
    rejected_by: str | None = None
    reject_reason: str | None = None


class BeingState(BaseModel):
    mode: WakeMode
    focus_mode: FocusMode = FocusMode.SLEEPING
    current_thought: str | None = None
    focus_subject: FocusSubject | None = None
    focus_effort: FocusEffort | None = None
    last_action: ToolExecutionResult | None = None
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None
    last_proactive_kind: str | None = None  # "follow_up" | "check_in" | "reflection" | "silent"
    browser_organ: BrowserOrganState | None = None
    browser_session: BrowserSessionState | None = None
    xhs_work_domain: XhsWorkDomainState | None = None
    # 升级计划书历史（最近 50 条，用于防重复和状态查询）
    upgrade_proposals: list[UpgradeProposal] = Field(default_factory=list)
    last_upgrade_proposal_at: datetime | None = None

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
