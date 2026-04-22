from datetime import datetime
from enum import Enum

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


class XhsWorkStatus(str, Enum):
    IDLE = "idle"
    IDLE_REVIEWING = "idle_reviewing"  # published, images pending
    SCOUTING = "scouting"
    DRAFTING = "drafting"
    PREPARING = "preparing"
    PUBLISHING = "publishing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"


class XhsPublishMode(str, Enum):
    REVIEW_BEFORE_PUBLISH = "review_before_publish"
    DIRECT_PUBLISH = "direct_publish"


class XhsWorkProfile(BaseModel):
    work_type: str = "xiaohongshu_operations"
    account_name: str = ""
    account_positioning: str = ""
    target_audience: str = ""
    expression_style: str = ""
    scouting_interval_hours: float = 1.0  # hours between scouting cycles
    publish_mode: XhsPublishMode = XhsPublishMode.REVIEW_BEFORE_PUBLISH
    auto_publish_selector: str = ""  # CSS selector for publish button; empty = auto-discover


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
    pending_drafts: list[dict] = Field(default_factory=list)  # [{"draft_id", "title", "body", "generated_at", "status"}]
    published_history: list[dict] = Field(default_factory=list)  # [{"draft_id", "title", "published_at", "post_url"}]


class XhsWorkGoals(BaseModel):
    north_star: str = ""
    weekly_goals: list[str] = []
    monthly_content_target: int = 0


class XhsWorkDomainState(BaseModel):
    profile: XhsWorkProfile = XhsWorkProfile()
    state: XhsWorkState = XhsWorkState()
    goals: XhsWorkGoals = XhsWorkGoals()


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

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
