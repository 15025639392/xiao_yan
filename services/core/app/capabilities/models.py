from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CapabilityName(str, Enum):
    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    FS_LIST = "fs.list"
    FS_SEARCH = "fs.search"
    SHELL_RUN = "shell.run"


class RiskLevel(str, Enum):
    SAFE = "safe"
    RESTRICTED = "restricted"
    DANGEROUS = "dangerous"


class CapabilityContext(BaseModel):
    reason: str | None = None


class CapabilityJobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CapabilityApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CapabilityApprovalAction(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class CapabilityRequest(BaseModel):
    request_id: str = Field(..., min_length=1)
    capability: CapabilityName
    args: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    requires_approval: bool = False
    approval_status: CapabilityApprovalStatus = CapabilityApprovalStatus.NOT_REQUIRED
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    rejection_reason: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=1)
    attempt: int = Field(default=1, ge=1, le=20)
    max_attempts: int = Field(default=3, ge=1, le=20)
    context: CapabilityContext = Field(default_factory=CapabilityContext)


class CapabilityAudit(BaseModel):
    executor: str = "desktop"
    started_at: str = Field(..., min_length=1)
    finished_at: str = Field(..., min_length=1)
    duration_ms: int = Field(..., ge=0)


class CapabilityResult(BaseModel):
    request_id: str = Field(..., min_length=1)
    ok: bool
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    audit: CapabilityAudit


class CapabilityDescriptor(BaseModel):
    name: CapabilityName
    default_risk_level: RiskLevel
    default_requires_approval: bool
    description: str
    current_binding: str


class CapabilityDispatchRequest(BaseModel):
    capability: CapabilityName
    args: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel | None = None
    requires_approval: bool | None = None
    idempotency_key: str | None = Field(default=None, min_length=1)
    max_attempts: int | None = Field(default=None, ge=1, le=20)
    context: CapabilityContext = Field(default_factory=CapabilityContext)


class CapabilityDispatchResponse(BaseModel):
    request_id: str
    status: CapabilityJobStatus
    queued_at: str


class CapabilityPendingItem(BaseModel):
    request: CapabilityRequest
    queued_at: str
    lease_expires_at: str


class CapabilityPendingResponse(BaseModel):
    items: list[CapabilityPendingItem]


class CapabilityCompleteResponse(BaseModel):
    request_id: str
    status: CapabilityJobStatus
    completed_at: str | None = None


class CapabilityJobSnapshot(BaseModel):
    request: CapabilityRequest
    status: CapabilityJobStatus
    queued_at: str
    completed_at: str | None = None
    result: CapabilityResult | None = None


class CapabilityQueueStatusResponse(BaseModel):
    pending: int
    pending_approval: int = 0
    in_progress: int
    completed: int
    dead_letter: int


class CapabilityJobAuditItem(BaseModel):
    request_id: str
    capability: CapabilityName
    status: CapabilityJobStatus
    queued_at: str
    completed_at: str | None = None
    attempt: int
    max_attempts: int
    approval_status: CapabilityApprovalStatus
    policy_version: str | None = None
    policy_revision: int | None = None
    executor: str | None = None
    ok: bool | None = None
    error_code: str | None = None
    dead_letter: bool = False


class CapabilityJobAuditResponse(BaseModel):
    items: list[CapabilityJobAuditItem]
    next_cursor: str | None = None


class CapabilityApprovalDecisionRequest(BaseModel):
    approver: str | None = Field(default=None, min_length=1)
    reason: str | None = None


class CapabilityApprovalDecisionResponse(BaseModel):
    request_id: str
    status: CapabilityJobStatus
    approval_status: CapabilityApprovalStatus
    completed_at: str | None = None


class CapabilityApprovalPendingItem(BaseModel):
    request: CapabilityRequest
    queued_at: str


class CapabilityApprovalPendingResponse(BaseModel):
    items: list[CapabilityApprovalPendingItem]


class CapabilityApprovalHistoryItem(BaseModel):
    request_id: str
    capability: CapabilityName
    action: CapabilityApprovalAction
    approver: str
    reason: str | None = None
    decided_at: str


class CapabilityApprovalHistoryResponse(BaseModel):
    items: list[CapabilityApprovalHistoryItem]


CAPABILITY_DESCRIPTORS: list[CapabilityDescriptor] = [
    CapabilityDescriptor(
        name=CapabilityName.FS_READ,
        default_risk_level=RiskLevel.SAFE,
        default_requires_approval=False,
        description="Read text content from an allowed path.",
        current_binding="chat file tool: read_file / tools files read endpoint",
    ),
    CapabilityDescriptor(
        name=CapabilityName.FS_LIST,
        default_risk_level=RiskLevel.SAFE,
        default_requires_approval=False,
        description="List files and directories under an allowed path.",
        current_binding="chat file tool: list_directory / tools files list endpoint",
    ),
    CapabilityDescriptor(
        name=CapabilityName.FS_SEARCH,
        default_risk_level=RiskLevel.RESTRICTED,
        default_requires_approval=False,
        description="Search text in files under an allowed path.",
        current_binding="chat file tool: search_files / tools files search endpoint",
    ),
    CapabilityDescriptor(
        name=CapabilityName.FS_WRITE,
        default_risk_level=RiskLevel.RESTRICTED,
        default_requires_approval=False,
        description="Write text content to an allowed path.",
        current_binding="chat file tool: write_file / tools files write endpoint",
    ),
    CapabilityDescriptor(
        name=CapabilityName.SHELL_RUN,
        default_risk_level=RiskLevel.RESTRICTED,
        default_requires_approval=True,
        description="Execute a shell command in the controlled sandbox.",
        current_binding="tools execute endpoint + command sandbox/runner",
    ),
]
