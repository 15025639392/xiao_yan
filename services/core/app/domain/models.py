from datetime import datetime
from enum import Enum

from pydantic import BaseModel
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

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
