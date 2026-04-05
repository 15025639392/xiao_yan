from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class FocusMode(str, Enum):
    SLEEPING = "sleeping"
    MORNING_PLAN = "morning_plan"
    AUTONOMY = "autonomy"
    SELF_IMPROVEMENT = "self_improvement"


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


class ActionResult(BaseModel):
    command: str
    output: str


class SelfImprovementStatus(str, Enum):
    PENDING = "pending"
    DIAGNOSING = "diagnosing"
    PATCHING = "patching"
    PENDING_APPROVAL = "pending_approval"  # Phase 6: 等待用户审批
    VERIFYING = "verifying"
    APPLIED = "applied"
    FAILED = "failed"
    REJECTED = "rejected"  # Phase 6: 用户拒绝


class SelfImprovementVerification(BaseModel):
    commands: list[str] = Field(default_factory=list)
    passed: bool = False
    summary: str | None = None


class EditKind(str, Enum):
    REPLACE = "replace"
    CREATE = "create"
    INSERT = "insert"


class SelfImprovementEdit(BaseModel):
    file_path: str
    search_text: str = ""
    replace_text: str = ""
    kind: EditKind = EditKind.REPLACE
    insert_after: str | None = None  # for INSERT kind: insert after this anchor text
    file_content: str | None = None  # for CREATE kind: full file content to write


class SelfImprovementJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    reason: str
    target_area: str
    status: SelfImprovementStatus
    spec: str
    patch_summary: str | None = None
    red_verification: SelfImprovementVerification | None = None
    verification: SelfImprovementVerification | None = None
    test_edits: list[SelfImprovementEdit] = Field(default_factory=list)
    edits: list[SelfImprovementEdit] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    cooldown_until: datetime | None = None

    # ── Phase 3: Git 工作流字段 ──────────────────────
    branch_name: str | None = None  # 本次自编程使用的分支名
    commit_hash: str | None = None  # commit 的完整 hash（短 hash 可截取）
    commit_message: str | None = None  # commit message 完整文本
    candidate_label: str | None = None  # 多候选模式下选中的方案标签

    # ── Phase 4: 沙箱 + 冲突检测字段 ───────────────────
    sandbox_prechecked: bool = False  # 是否经过了沙箱预验证
    sandbox_result: str | None = None  # 预验结果摘要
    conflict_severity: str = "safe"  # 冲突检测结果：safe / warning / blocking
    conflict_details: str | None = None  # 冲突详情

    # ── Phase 5: 回滚恢复 + 健康度字段 ──────────────────
    health_score: float | None = None  # 健康检查总分 (0~100)
    health_grade: str | None = None   # 健康等级：excellent/good/fair/poor/critical
    rollback_info: str | None = None  # 回滚信息（如果发生过回滚）
    snapshot_taken: bool = False     # 是否在 apply 前创建了差异快照

    # ── Phase 6: 审批字段 ──────────────────────────────
    approval_requested_at: datetime | None = None  # 发起审批请求的时间
    approval_edits_summary: str | None = None      # 供用户审批查看的编辑摘要
    approval_reason: str | None = None             # 拒绝原因（用户填写）


class BeingState(BaseModel):
    mode: WakeMode
    focus_mode: FocusMode = FocusMode.SLEEPING
    current_thought: str | None = None
    active_goal_ids: list[str] = Field(default_factory=list)
    today_plan: TodayPlan | None = None
    last_action: ActionResult | None = None
    self_improvement_job: SelfImprovementJob | None = None
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
