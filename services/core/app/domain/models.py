from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field
from app.tools.models import ToolExecutionResult


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class FocusMode(str, Enum):
    SLEEPING = "sleeping"
    MORNING_PLAN = "morning_plan"
    AUTONOMY = "autonomy"
    SELF_IMPROVEMENT = "self_programming"


class TodayPlanStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class TodayPlanStepKind(str, Enum):
    REFLECT = "reflect"
    ACTION = "action"


class TodayPlanStep(BaseModel):
    content: str
    status: TodayPlanStepStatus = TodayPlanStepStatus.PENDING
    kind: TodayPlanStepKind = TodayPlanStepKind.REFLECT
    command: str | None = None


class TodayPlan(BaseModel):
    goal_id: str
    goal_title: str
    steps: list[TodayPlanStep] = Field(default_factory=list)


class SelfProgrammingStatus(str, Enum):
    DRAFTED = "drafted"
    PENDING_START_APPROVAL = "pending_start_approval"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FROZEN = "frozen"
    PENDING = "pending"
    DIAGNOSING = "diagnosing"
    PATCHING = "patching"
    PENDING_APPROVAL = "pending_approval"
    VERIFYING = "verifying"
    APPLIED = "applied"
    FAILED = "failed"
    REJECTED = "rejected"


class SelfProgrammingVerification(BaseModel):
    commands: list[str] = Field(default_factory=list)
    passed: bool = False
    summary: str | None = None


class EditKind(str, Enum):
    REPLACE = "replace"
    CREATE = "create"
    INSERT = "insert"


class SelfProgrammingEdit(BaseModel):
    file_path: str
    search_text: str = ""
    replace_text: str = ""
    kind: EditKind = EditKind.REPLACE
    insert_after: str | None = None
    file_content: str | None = None


class SelfProgrammingJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    reason: str
    reason_statement: str | None = None
    direction_statement: str | None = None
    target_area: str
    status: SelfProgrammingStatus
    queue_status: str | None = None
    owner_type: str | None = None
    delegate_provider: str | None = None
    delegate_run_id: str | None = None
    execution_workspace: str | None = None
    risk_level: str | None = None
    promotion_status: str | None = None
    frozen_reason: str | None = None
    spec: str
    patch_summary: str | None = None
    red_verification: SelfProgrammingVerification | None = None
    verification: SelfProgrammingVerification | None = None
    test_edits: list[SelfProgrammingEdit] = Field(default_factory=list)
    edits: list[SelfProgrammingEdit] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    cooldown_until: datetime | None = None

    # Git 执行信息
    branch_name: str | None = None
    commit_hash: str | None = None
    commit_message: str | None = None
    candidate_label: str | None = None

    # 预检与冲突信息
    sandbox_prechecked: bool = False
    sandbox_result: str | None = None
    conflict_severity: str = "safe"
    conflict_details: str | None = None

    # 验证与回滚信息
    health_score: float | None = None
    health_grade: str | None = None
    rollback_info: str | None = None
    snapshot_taken: bool = False

    # 审批信息
    approval_requested_at: datetime | None = None
    approval_edits_summary: str | None = None
    approval_reason: str | None = None
    start_approval_reason: str | None = None
    start_approved_by: str | None = None
    start_approved_at: datetime | None = None

    # 拒绝审计
    rejection_phase: str | None = None
    rejection_reason: str | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None

    # 冷却快照
    cooldown_policy_snapshot: dict[str, int] | None = None


class BeingState(BaseModel):
    mode: WakeMode
    focus_mode: FocusMode = FocusMode.SLEEPING
    current_thought: str | None = None
    active_goal_ids: list[str] = Field(default_factory=list)
    today_plan: TodayPlan | None = None
    last_action: ToolExecutionResult | None = None
    self_programming_job: SelfProgrammingJob | None = None
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
