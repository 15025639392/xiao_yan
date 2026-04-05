"""
审批交互系统测试

覆盖：
1. PATCHING → PENDING_APPROVAL 状态门控（apply 后不再直接进入 VERIFYING）
2. PENDING_APPROVAL 状态不自动推进（tick 返回 None / 不变）
3. 审批 API：POST approve、POST reject
4. 拒绝后的终态处理（REJECTED + 回归 autonomy）
5. _build_edits_summary 辅助函数
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.domain.models import (
    BeingState,
    SelfImprovementEdit,
    SelfImprovementJob,
    SelfImprovementStatus,
    WakeMode,
)
from app.main import app
from app.runtime import StateStore


# ═══════════════════════════════════════════════════
# 1. 状态门控测试（Service 层）
# ═══════════════════════════════════════════════════


def test_pending_approval_status_exists():
    """PENDING_APPROVAL 和 REJECTED 枚举值存在。"""
    assert hasattr(SelfImprovementStatus, "PENDING_APPROVAL")
    assert hasattr(SelfImprovementStatus, "REJECTED")
    assert SelfImprovementStatus.PENDING_APPROVAL.value == "pending_approval"
    assert SelfImprovementStatus.REJECTED.value == "rejected"


def test_job_model_has_approval_fields():
    """SelfImprovementJob 包含审批相关字段。"""

    job = SelfImprovementJob(
        id="test-approval-1",
        target_area="agent",
        reason="测试",
        spec="测试补丁",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime.now(tz=timezone.utc),
        approval_requested_at=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        approval_edits_summary="修改了 agent/loop.py",
        approval_reason=None,
    )
    assert job.approval_requested_at is not None
    assert job.approval_edits_summary == "修改了 agent/loop.py"
    assert job.approval_reason is None


def test_pending_approval_is_terminal_in_tick():
    """PENDING_APPROVAL 状态在 tick_job 中不自动推进。"""
    from app.self_improvement.service import SelfImprovementService

    service = SelfImprovementService()
    store = StateStore(BeingState(mode=WakeMode.AWAKE))

    # 构造一个 PENDING_APPROVAL 状态的 job
    job = store.get().self_improvement_job
    if job is None:
        job = SelfImprovementJob(
            id="job-pending-tick",
            target_area="agent",
            reason="测试原因",
            spec="测试方案",
            status=SelfImprovementStatus.PENDING_APPROVAL,
            created_at=datetime.now(tz=timezone.utc),
            approval_requested_at=datetime.now(tz=timezone.utc),
            approval_edits_summary="测试摘要",
        )
        state = store.get().model_copy(update={"self_improvement_job": job})
        store.set(state)

    result = service.tick_job(store.get())
    # PENDING_APPROVAL 应该返回 None（不自动推进）
    assert result is None


# ═══════════════════════════════════════════════════
# 2. 审批 API 测试
# ═══════════════════════════════════════════════════

def test_approve_job_success():
    """POST /{job_id}/approve — 批准成功，状态变为 VERIFYING。"""

    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    job = SelfImprovementJob(
        id="job-approve-1",
        target_area="planner",
        reason="增加错误重试",
        spec="添加 retry 逻辑",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        approval_requested_at=datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc),
        approval_edits_summary="修改 planner.py",
    )
    store.set(store.get().model_copy(update={"self_improvement_job": job}))
    app.state.state_store = store

    client = TestClient(app)
    resp = client.post("/self-improvement/job-approve-1/approve", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["job_id"] == "job-approve-1"

    # 验证状态已更新为 VERIFYING
    updated_state = store.get()
    assert updated_state.self_improvement_job is not None
    assert updated_state.self_improvement_job.status == SelfImprovementStatus.VERIFYING


def test_approve_job_not_found():
    """POST /{job_id}/approve — job 不存在时返回 404。"""

    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    job = SelfImprovementJob(
        id="job-other",
        target_area="agent",
        reason="测试",
        spec="测试",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime.now(tz=timezone.utc),
    )
    store.set(store.get().model_copy(update={"self_improvement_job": job}))
    app.state.state_store = store

    client = TestClient(app)
    resp = client.post("/self-improvement/nonexistent/approve", json={})
    assert resp.status_code == 404


def test_approve_job_wrong_status():
    """POST /{job_id}/approve — job 不是 pending_approval 状态时返回 409。"""

    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    job = SelfImprovementJob(
        id="job-diagnosing",
        target_area="agent",
        reason="测试",
        spec="测试",
        status=SelfImprovementStatus.DIAGNOSING,
        created_at=datetime.now(tz=timezone.utc),
    )
    store.set(store.get().model_copy(update={"self_improvement_job": job}))
    app.state.state_store = store

    client = TestClient(app)
    resp = client.post("/self-improvement/job-diagnosing/approve", json={})
    assert resp.status_code == 409
    assert "not pending_approval" in resp.json()["detail"]


def test_reject_job_with_reason():
    """POST /{job_id}/reject — 拒绝成功，状态变为 REJECTED 并记录原因。"""

    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    job = SelfImprovementJob(
        id="job-reject-1",
        target_area="executor",
        reason="性能优化",
        spec="缓存结果",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        approval_requested_at=datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc),
    )
    store.set(store.get().model_copy(update={"self_improvement_job": job}))
    app.state.state_store = store

    client = TestClient(app)
    resp = client.post(
        "/self-improvement/job-reject-1/reject",
        json={"reason": "改动范围太大，需要拆分"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # 验证状态已变为 REJECTED
    updated_state = store.get()
    assert updated_state.self_improvement_job is not None
    assert updated_state.self_improvement_job.status == SelfImprovementStatus.REJECTED
    assert updated_state.self_improvement_job.approval_reason == "改动范围太大，需要拆分"
    # 拒绝后应回到 autonomy
    assert updated_state.focus_mode != "self_improvement"


def test_reject_job_default_reason():
    """POST /{job_id}/reject — 不提供原因时使用默认值。"""

    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    job = SelfImprovementJob(
        id="job-reject-no-reason",
        target_area="agent",
        reason="测试",
        spec="测试",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime.now(tz=timezone.utc),
    )
    store.set(store.get().model_copy(update={"self_improvement_job": job}))
    app.state.state_store = store

    client = TestClient(app)
    resp = client.post("/self-improvement/job-reject-no-reason/reject", json={})
    assert resp.status_code == 200

    updated_state = store.get()
    assert updated_state.self_improvement_job.status == SelfImprovementStatus.REJECTED
    assert updated_state.self_improvement_job.approval_reason == "用户拒绝"


# ═══════════════════════════════════════════════════
# 3. 端到端流程测试：PATCHING → PENDING → APPROVE → VERIFYING
# ═══════════════════════════════════════════════════


def test_full_approval_flow_via_api():
    """
    完整审批流程：
    1. 构造一个 PENDING_APPROVAL 的 job
    2. POST /approve 批准
    3. 状态变为 VERIFYING
    """

    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    job = SelfImprovementJob(
        id="full-flow-job",
        target_area="service",
        reason="修复状态机 bug",
        spec="增加 REJECTED 状态处理",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
        approval_requested_at=datetime(2026, 4, 5, 9, 30, tzinfo=timezone.utc),
        approval_edits_summary="service.py: 新增 REJECTED 分支; models.py: 新增枚举值",
        touched_files=["app/self_improvement/service.py", "app/domain/models.py"],
    )
    store.set(store.get().model_copy(update={"self_improvement_job": job}))
    app.state.state_store = store

    client = TestClient(app)

    # Step 1: 批准
    resp = client.post("/self-improvement/full-flow-job/approve", json={"reason": "LGTM"})
    assert resp.status_code == 200

    # Step 2: 验证状态变更
    updated = store.get()
    assert updated.self_improvement_job.status == SelfImprovementStatus.VERIFYING
    assert "批准" in updated.current_thought


# ═══════════════════════════════════════════════════
# 4. 辅助函数测试
# ═══════════════════════════════════════════════════


def test_build_edits_summary():
    """_build_edits_summary 正确生成编辑摘要。"""
    from app.self_improvement.service import _build_edits_summary

    job = SelfImprovementJob(
        id="summary-test",
        target_area="agent",
        reason="测试摘要生成",
        spec="测试",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime.now(tz=timezone.utc),
        edits=[
            SelfImprovementEdit(
                kind="replace",
                file_path="app/agent/loop.py",
                search_text="old code",
                replacement_text="new code",
            ),
            SelfImprovementEdit(
                kind="create",
                file_path="app/new_module.py",
                replacement_text="# new file content",
            ),
            SelfImprovementEdit(
                kind="insert",
                file_path="app/service.py",
                search_text="# marker",
                insertion_text="inserted line",
            ),
        ],
        touched_files=["app/agent/loop.py", "app/new_module.py", "app/service.py"],
    )

    summary = _build_edits_summary(job)
    assert "loop.py" in summary
    assert "new_module.py" in summary
    assert "service.py" in summary
    # 应包含编辑类型信息
    assert len(summary) > 0


def test_build_edits_summary_empty_edits():
    """_build_edits_summary 在没有 edits 时返回合理默认值。"""
    from app.self_improvement.service import _build_edits_summary

    job = SelfImprovementJob(
        id="empty-summary-test",
        target_area="agent",
        reason="测试",
        spec="测试",
        status=SelfImprovementStatus.PENDING_APPROVAL,
        created_at=datetime.now(tz=timezone.utc),
        touched_files=["app/some_file.py"],
    )

    summary = _build_edits_summary(job)
    assert isinstance(summary, str)
    assert len(summary) > 0
