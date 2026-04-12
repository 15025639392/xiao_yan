from datetime import datetime
from enum import Enum
from typing import Any
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
    ORCHESTRATOR = "orchestrator"


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


class OrchestratorTaskKind(str, Enum):
    ANALYZE = "analyze"
    IMPLEMENT = "implement"
    TEST = "test"
    VERIFY = "verify"
    SUMMARIZE = "summarize"


class OrchestratorTaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestratorSessionStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    PENDING_PLAN_APPROVAL = "pending_plan_approval"
    DISPATCHING = "dispatching"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestratorCoordinationMode(str, Enum):
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    QUEUED = "queued"
    PREEMPTED = "preempted"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestratorFailureCategory(str, Enum):
    DELEGATE_FAILURE = "delegate_failure"
    VERIFICATION_FAILURE = "verification_failure"
    POLICY_VIOLATION = "policy_violation"


class DelegateCommandResult(BaseModel):
    command: str
    success: bool = False
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: int | None = None


class OrchestratorVerification(BaseModel):
    commands: list[str] = Field(default_factory=list)
    command_results: list[DelegateCommandResult] = Field(default_factory=list)
    passed: bool = False
    summary: str | None = None


class ProjectSnapshot(BaseModel):
    project_path: str
    project_name: str
    repository_root: str
    languages: list[str] = Field(default_factory=list)
    package_manager: str | None = None
    framework: str | None = None
    entry_files: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    key_directories: list[str] = Field(default_factory=list)


class OrchestratorDelegateRequest(BaseModel):
    objective: str
    project_path: str
    scope_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)
    acceptance_commands: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class OrchestratorDelegateDebugInfo(BaseModel):
    stderr_excerpt: str | None = None
    last_jsonl_event: dict[str, Any] | None = None


class OrchestratorDelegateResult(BaseModel):
    status: str
    summary: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    command_results: list[DelegateCommandResult] = Field(default_factory=list)
    followup_needed: list[str] = Field(default_factory=list)
    error: str | None = None
    debug: OrchestratorDelegateDebugInfo | None = None


class OrchestratorTaskStallFollowup(BaseModel):
    level: str = "soft_ping"
    elapsed_minutes: int | None = None
    manager_summary: str | None = None
    engineer_prompt: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    followup_command: str | None = None


class OrchestratorTask(BaseModel):
    task_id: str
    title: str
    kind: OrchestratorTaskKind
    scope_paths: list[str] = Field(default_factory=list)
    acceptance_commands: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    delegate_target: str = "codex"
    status: OrchestratorTaskStatus = OrchestratorTaskStatus.PENDING
    result_summary: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    delegate_run_id: str | None = None
    assignment_source: str | None = None
    assignment_directive: str | None = None
    assignment_requested_objective: str | None = None
    assignment_scope_override: list[str] | None = None
    assignment_resolved_scope_override: list[str] | None = None
    assignment_acceptance_override: list[str] | None = None
    assignment_priority_override: int | None = None
    engineer_id: int | None = None
    engineer_label: str | None = None
    assigned_at: datetime | None = None
    stall_level: str | None = None
    stall_followup: OrchestratorTaskStallFollowup | None = None
    last_stall_followup_at: datetime | None = None
    last_intervened_at: datetime | None = None
    intervention_suggestions: list[str] = Field(default_factory=list)
    error: str | None = None


class OrchestratorPlan(BaseModel):
    objective: str
    constraints: list[str] = Field(default_factory=list)
    definition_of_done: list[str] = Field(default_factory=list)
    project_snapshot: ProjectSnapshot
    tasks: list[OrchestratorTask] = Field(default_factory=list)


class OrchestratorDelegateRun(BaseModel):
    task_id: str
    delegate_run_id: str
    provider: str = "codex"
    status: str = "running"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class OrchestratorSessionCoordination(BaseModel):
    mode: OrchestratorCoordinationMode = OrchestratorCoordinationMode.IDLE
    priority_score: int = 0
    queue_position: int | None = None
    waiting_reason: str | None = None
    failure_category: OrchestratorFailureCategory | None = None
    preempted_by_session_id: str | None = None
    dispatch_slot: int | None = None


class OrchestratorSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    project_path: str
    project_name: str
    goal: str
    priority_bias: int = 0
    status: OrchestratorSessionStatus = OrchestratorSessionStatus.DRAFT
    plan: OrchestratorPlan | None = None
    delegates: list[OrchestratorDelegateRun] = Field(default_factory=list)
    coordination: OrchestratorSessionCoordination | None = None
    verification: OrchestratorVerification | None = None
    summary: str | None = None
    entered_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrchestratorDelegateCompletionPayload(BaseModel):
    session_id: str
    task_id: str
    delegate_run_id: str
    result: OrchestratorDelegateResult


class OrchestratorDelegateStopPayload(BaseModel):
    session_id: str
    task_id: str
    delegate_run_id: str
    reason: str | None = None


class OrchestratorVerificationRollup(BaseModel):
    total_sessions: int = 0
    passed_sessions: int = 0
    failed_sessions: int = 0
    pending_sessions: int = 0


class OrchestratorSchedulerSnapshot(BaseModel):
    max_parallel_sessions: int = 2
    running_sessions: int = 0
    available_slots: int = 0
    queued_sessions: int = 0
    active_session_id: str | None = None
    running_session_ids: list[str] = Field(default_factory=list)
    queued_session_ids: list[str] = Field(default_factory=list)
    verification_rollup: OrchestratorVerificationRollup = Field(default_factory=OrchestratorVerificationRollup)
    policy_note: str | None = None


class BeingState(BaseModel):
    mode: WakeMode
    focus_mode: FocusMode = FocusMode.SLEEPING
    current_thought: str | None = None
    active_goal_ids: list[str] = Field(default_factory=list)
    today_plan: TodayPlan | None = None
    last_action: ToolExecutionResult | None = None
    self_programming_job: SelfProgrammingJob | None = None
    orchestrator_session: OrchestratorSession | None = None
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
