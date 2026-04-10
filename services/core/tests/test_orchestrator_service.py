from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app.domain.models import (
    BeingState,
    OrchestratorCoordinationMode,
    OrchestratorDelegateCompletionPayload,
    OrchestratorDelegateResult,
    OrchestratorFailureCategory,
    OrchestratorSessionCoordination,
    OrchestratorSessionStatus,
    OrchestratorVerification,
    WakeMode,
)
from app.memory.repository import InMemoryMemoryRepository
from app.orchestrator.conversation_repository import OrchestratorConversationRepository
from app.orchestrator.conversation_service import OrchestratorConversationService
from app.orchestrator.delegate_contract import build_delegate_request
from app.orchestrator.repository import OrchestratorSessionRepository
from app.orchestrator.service import OrchestratorService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config


@pytest.fixture(autouse=True)
def clear_folder_permissions() -> None:
    config = get_runtime_config()
    config.clear_folder_permissions()
    yield
    config.clear_folder_permissions()


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    project = tmp_path / "demo-project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "main.ts").write_text("console.log('hello')\n", encoding="utf-8")
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "demo-project",
                "scripts": {
                    "test": "vitest run",
                    "build": "vite build",
                },
                "dependencies": {
                    "vite": "^5.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    return project


@pytest.fixture()
def orchestrator_service(project_dir: Path) -> OrchestratorService:
    config = get_runtime_config()
    config.set_folder_permission(str(project_dir), "full_access")
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=InMemoryMemoryRepository(),
    )
    repository = OrchestratorSessionRepository(in_memory=True)

    def verification_runner(_project_path: str, commands: list[str]) -> OrchestratorVerification:
        return OrchestratorVerification(
            commands=commands,
            passed=True,
            summary=f"验证通过，共执行 {len(commands)} 条命令。",
        )

    return OrchestratorService(
        repository=repository,
        state_store=state_store,
        verification_runner=verification_runner,
    )


def test_create_session_rejects_project_outside_imported_registry(tmp_path: Path) -> None:
    state_store = StateStore(initial_state=BeingState(mode=WakeMode.AWAKE), memory_repository=InMemoryMemoryRepository())
    service = OrchestratorService(
        repository=OrchestratorSessionRepository(in_memory=True),
        state_store=state_store,
        verification_runner=lambda _path, commands: OrchestratorVerification(commands=commands, passed=True),
    )

    with pytest.raises(ValueError, match="imported project"):
        service.create_session("进入主控，处理当前项目", str(tmp_path / "missing-project"))


def test_generate_plan_contains_required_fields(orchestrator_service: OrchestratorService, project_dir: Path) -> None:
    session = orchestrator_service.create_session("进入主控，梳理启动链路", str(project_dir))
    planned = orchestrator_service.generate_plan(session.session_id)

    assert planned.plan is not None
    assert planned.status.value == "pending_plan_approval"
    assert planned.plan.objective == "进入主控，梳理启动链路"
    assert planned.plan.definition_of_done
    task_kinds = [task.kind.value for task in planned.plan.tasks]
    assert task_kinds[0] == "analyze"
    assert task_kinds[-2:] == ["verify", "summarize"]
    assert task_kinds.count("implement") >= 1
    implement_ids = [task.task_id for task in planned.plan.tasks if task.kind.value == "implement"]
    verify_task = next(task for task in planned.plan.tasks if task.kind.value == "verify")
    assert verify_task.depends_on == implement_ids
    delegate_request = build_delegate_request(
        goal=planned.goal,
        project_path=planned.project_path,
        task=planned.plan.tasks[0],
    )
    command_result_schema = delegate_request.output_schema["properties"]["command_results"]["items"]
    assert command_result_schema["required"] == [
        "command",
        "success",
        "exit_code",
        "stdout",
        "stderr",
        "duration_ms",
    ]


def test_generate_plan_splits_implementation_tasks_for_tauri_project(tmp_path: Path) -> None:
    project = tmp_path / "demo-tauri-project"
    (project / "src").mkdir(parents=True)
    (project / "src-tauri" / "src").mkdir(parents=True)
    (project / "src" / "main.ts").write_text("console.log('frontend')\n", encoding="utf-8")
    (project / "src-tauri" / "Cargo.toml").write_text(
        "[package]\nname = \"demo-tauri\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    (project / "package.json").write_text(
        json.dumps({"name": "demo-tauri-project", "scripts": {"build": "vite build"}}),
        encoding="utf-8",
    )

    config = get_runtime_config()
    config.set_folder_permission(str(project), "full_access")
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=InMemoryMemoryRepository(),
    )
    service = OrchestratorService(
        repository=OrchestratorSessionRepository(in_memory=True),
        state_store=state_store,
        verification_runner=lambda _path, commands: OrchestratorVerification(commands=commands, passed=True),
    )

    session = service.create_session("进入主控，升级当前项目", str(project))
    planned = service.generate_plan(session.session_id)
    assert planned.plan is not None

    implement_tasks = [task for task in planned.plan.tasks if task.kind.value == "implement"]
    assert len(implement_tasks) >= 2
    flattened_scope = {path for task in implement_tasks for path in task.scope_paths}
    assert "src" in flattened_scope
    assert "src-tauri" in flattened_scope


def test_summarize_task_is_completed_locally_without_delegate(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    session = orchestrator_service.generate_plan(session.session_id)
    session = orchestrator_service.approve_plan(session.session_id)

    while session.status.value not in {"completed", "failed"}:
        session = orchestrator_service.dispatch(session.session_id)
        assert session.plan is not None
        running_tasks = [task for task in session.plan.tasks if task.status.value == "running"]
        if not running_tasks:
            break
        running_task = running_tasks[0]
        changed_files = ["src/main.ts"] if running_task.kind.value == "implement" else []
        session = orchestrator_service.complete_delegate(
            OrchestratorDelegateCompletionPayload(
                session_id=session.session_id,
                task_id=running_task.task_id,
                delegate_run_id=running_task.delegate_run_id or "",
                result=OrchestratorDelegateResult(
                    status="succeeded",
                    summary=f"{running_task.title} 完成",
                    changed_files=changed_files,
                ),
            )
        )

    assert session.plan is not None
    summarize = next(task for task in session.plan.tasks if task.kind.value == "summarize")
    assert summarize.status.value == "succeeded"
    assert summarize.delegate_run_id is None
    assert all(item.task_id != summarize.task_id for item in session.delegates)


def test_dispatch_blocks_high_risk_implement_until_secondary_approval(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    session = orchestrator_service.generate_plan(session.session_id)
    session = orchestrator_service.apply_directive(session.session_id, "把 scope 限制在 当前项目")
    session = orchestrator_service.approve_plan(session.session_id)

    session = orchestrator_service.dispatch(session.session_id)
    analyze_task = next(task for task in session.plan.tasks if task.status.value == "running")
    session = orchestrator_service.complete_delegate(
        OrchestratorDelegateCompletionPayload(
            session_id=session.session_id,
            task_id=analyze_task.task_id,
            delegate_run_id=analyze_task.delegate_run_id or "",
            result=OrchestratorDelegateResult(
                status="succeeded",
                summary="分析完成",
                changed_files=[],
            ),
        )
    )

    blocked = orchestrator_service.dispatch(session.session_id)
    assert blocked.status.value == "dispatching"
    assert blocked.coordination is not None
    assert "高风险" in (blocked.coordination.waiting_reason or "")
    blocked_implement = next(task for task in blocked.plan.tasks if task.kind.value == "implement")
    assert blocked_implement.status.value == "queued"

    approved = orchestrator_service.apply_directive(blocked.session_id, "批准高风险任务并继续")
    assert "高风险任务" in (approved.summary or "")
    approved_implement = next(task for task in approved.plan.tasks if task.kind.value == "implement")
    assert approved_implement.status.value == "pending"
    assert approved_implement.artifacts.get("secondary_approval_granted") is True


def test_dispatch_requires_plan_approval(orchestrator_service: OrchestratorService, project_dir: Path) -> None:
    session = orchestrator_service.create_session("进入主控，梳理启动链路", str(project_dir))
    planned = orchestrator_service.generate_plan(session.session_id)

    with pytest.raises(ValueError, match="not dispatchable"):
        orchestrator_service.dispatch(planned.session_id)


def test_multiple_sessions_can_coexist_and_be_activated(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
    tmp_path: Path,
) -> None:
    second_project = tmp_path / "demo-project-2"
    second_project.mkdir()
    (second_project / "package.json").write_text(json.dumps({"name": "demo-project-2"}), encoding="utf-8")
    get_runtime_config().set_folder_permission(str(second_project), "read_only")

    first = orchestrator_service.create_session("进入主控，处理项目一", str(project_dir))
    second = orchestrator_service.create_session("进入主控，处理项目二", str(second_project))

    sessions = orchestrator_service.list_sessions()
    assert {item.session_id for item in sessions} == {first.session_id, second.session_id}

    activated = orchestrator_service.activate_session(first.session_id)
    assert activated.session_id == first.session_id


def test_delegate_completion_advances_session_to_completed(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    session = orchestrator_service.generate_plan(session.session_id)
    session = orchestrator_service.approve_plan(session.session_id)

    while session.status.value != "completed":
        session = orchestrator_service.dispatch(session.session_id)
        assert session.plan is not None
        running_task = next(task for task in session.plan.tasks if task.status.value == "running")
        changed_files = ["src/main.ts"] if running_task.kind.value == "implement" else []
        session = orchestrator_service.complete_delegate(
            OrchestratorDelegateCompletionPayload(
                session_id=session.session_id,
                task_id=running_task.task_id,
                delegate_run_id=running_task.delegate_run_id or "",
                result=OrchestratorDelegateResult(
                    status="succeeded",
                    summary=f"{running_task.title} 完成",
                    changed_files=changed_files,
                ),
            )
        )

    assert session.status.value == "completed"
    assert session.verification is not None
    assert session.verification.passed is True


def test_delegate_out_of_scope_change_marks_session_failed(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    session = orchestrator_service.generate_plan(session.session_id)
    session = orchestrator_service.approve_plan(session.session_id)

    session = orchestrator_service.dispatch(session.session_id)
    analyze_task = next(task for task in session.plan.tasks if task.status.value == "running")
    session = orchestrator_service.complete_delegate(
        OrchestratorDelegateCompletionPayload(
            session_id=session.session_id,
            task_id=analyze_task.task_id,
            delegate_run_id=analyze_task.delegate_run_id or "",
            result=OrchestratorDelegateResult(
                status="succeeded",
                summary="分析完成",
                changed_files=[],
            ),
        )
    )

    session = orchestrator_service.dispatch(session.session_id)
    implement_task = next(task for task in session.plan.tasks if task.status.value == "running")
    failed = orchestrator_service.complete_delegate(
        OrchestratorDelegateCompletionPayload(
            session_id=session.session_id,
            task_id=implement_task.task_id,
            delegate_run_id=implement_task.delegate_run_id or "",
            result=OrchestratorDelegateResult(
                status="succeeded",
                summary="实现完成",
                changed_files=["README.md"],
            ),
        )
    )

    assert failed.status.value == "failed"
    assert failed.plan is not None
    failed_task = next(task for task in failed.plan.tasks if task.task_id == implement_task.task_id)
    assert failed_task.status.value == "failed"
    assert failed_task.error is not None
    assert "outside approved scope" in failed_task.error
    assert failed.coordination is not None
    assert failed.coordination.failure_category == "policy_violation"


def test_scheduler_tick_limits_parallel_dispatch_and_queues_lower_priority_sessions(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
    tmp_path: Path,
) -> None:
    second_project = tmp_path / "demo-project-2"
    third_project = tmp_path / "demo-project-3"
    second_project.mkdir()
    third_project.mkdir()
    (second_project / "package.json").write_text(json.dumps({"name": "demo-project-2"}), encoding="utf-8")
    (third_project / "package.json").write_text(json.dumps({"name": "demo-project-3"}), encoding="utf-8")
    get_runtime_config().set_folder_permission(str(second_project), "read_only")
    get_runtime_config().set_folder_permission(str(third_project), "read_only")

    first = orchestrator_service.approve_plan(
        orchestrator_service.generate_plan(
            orchestrator_service.create_session("进入主控，处理项目一", str(project_dir)).session_id
        ).session_id
    )
    second = orchestrator_service.approve_plan(
        orchestrator_service.generate_plan(
            orchestrator_service.create_session("进入主控，处理项目二", str(second_project)).session_id
        ).session_id
    )
    third = orchestrator_service.approve_plan(
        orchestrator_service.generate_plan(
            orchestrator_service.create_session("进入主控，处理项目三", str(third_project)).session_id
        ).session_id
    )

    orchestrator_service.activate_session(third.session_id)
    snapshot = orchestrator_service.run_scheduler_tick()

    assert snapshot.max_parallel_sessions == 2
    assert snapshot.running_sessions == 2
    assert third.session_id in snapshot.running_session_ids
    assert len(snapshot.queued_session_ids) == 1

    sessions = {item.session_id: item for item in orchestrator_service.list_sessions()}
    queued_session_id = snapshot.queued_session_ids[0]
    queued_session = sessions[queued_session_id]
    assert queued_session.plan is not None
    queued_task = next(task for task in queued_session.plan.tasks if task.task_id == "analyze-1")
    assert queued_task.status.value == "queued"
    assert queued_session.coordination is not None
    assert queued_session.coordination.mode.value in {"queued", "preempted"}
    assert queued_session.coordination.queue_position == 1
    assert queued_session.coordination.waiting_reason is not None


def test_scheduler_tick_prefers_active_session_without_interrupting_running_delegate(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
    tmp_path: Path,
) -> None:
    second_project = tmp_path / "demo-project-2"
    third_project = tmp_path / "demo-project-3"
    second_project.mkdir()
    third_project.mkdir()
    (second_project / "package.json").write_text(json.dumps({"name": "demo-project-2"}), encoding="utf-8")
    (third_project / "package.json").write_text(json.dumps({"name": "demo-project-3"}), encoding="utf-8")
    get_runtime_config().set_folder_permission(str(second_project), "read_only")
    get_runtime_config().set_folder_permission(str(third_project), "read_only")

    first = orchestrator_service.approve_plan(
        orchestrator_service.generate_plan(
            orchestrator_service.create_session("进入主控，处理项目一", str(project_dir)).session_id
        ).session_id
    )
    second = orchestrator_service.approve_plan(
        orchestrator_service.generate_plan(
            orchestrator_service.create_session("进入主控，处理项目二", str(second_project)).session_id
        ).session_id
    )
    third = orchestrator_service.approve_plan(
        orchestrator_service.generate_plan(
            orchestrator_service.create_session("进入主控，处理项目三", str(third_project)).session_id
        ).session_id
    )

    orchestrator_service.activate_session(first.session_id)
    orchestrator_service.run_scheduler_tick()
    orchestrator_service.activate_session(third.session_id)

    snapshot = orchestrator_service.run_scheduler_tick()
    sessions = {item.session_id: item for item in orchestrator_service.list_sessions()}

    assert snapshot.running_sessions == 2
    assert first.session_id in snapshot.running_session_ids
    assert second.session_id in snapshot.running_session_ids
    assert third.session_id not in snapshot.running_session_ids

    waiting_session = sessions[third.session_id]
    assert waiting_session.status == OrchestratorSessionStatus.DISPATCHING
    assert waiting_session.coordination is not None
    assert waiting_session.coordination.mode == "queued"
    assert waiting_session.coordination.preempted_by_session_id is None
    assert "不会抢占正在运行的 delegate" in (waiting_session.coordination.waiting_reason or "")


def test_scheduler_snapshot_rolls_up_verification_across_sessions(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
    tmp_path: Path,
) -> None:
    second_project = tmp_path / "demo-project-2"
    third_project = tmp_path / "demo-project-3"
    second_project.mkdir()
    third_project.mkdir()
    (second_project / "package.json").write_text(json.dumps({"name": "demo-project-2"}), encoding="utf-8")
    (third_project / "package.json").write_text(json.dumps({"name": "demo-project-3"}), encoding="utf-8")
    get_runtime_config().set_folder_permission(str(second_project), "read_only")
    get_runtime_config().set_folder_permission(str(third_project), "read_only")

    completed = orchestrator_service.create_session("进入主控，升级项目一", str(project_dir))
    completed = orchestrator_service.generate_plan(completed.session_id)
    completed = orchestrator_service.approve_plan(completed.session_id)
    while completed.status.value != "completed":
        completed = orchestrator_service.dispatch(completed.session_id)
        running_task = next(task for task in completed.plan.tasks if task.status.value == "running")
        completed = orchestrator_service.complete_delegate(
            OrchestratorDelegateCompletionPayload(
                session_id=completed.session_id,
                task_id=running_task.task_id,
                delegate_run_id=running_task.delegate_run_id or "",
                result=OrchestratorDelegateResult(
                    status="succeeded",
                    summary=f"{running_task.title} 完成",
                    changed_files=["src/main.ts"] if running_task.kind.value == "implement" else [],
                ),
            )
        )

    failed = orchestrator_service.create_session("进入主控，升级项目二", str(second_project))
    failed = orchestrator_service.generate_plan(failed.session_id)
    failed = orchestrator_service.approve_plan(failed.session_id)
    failed = orchestrator_service.dispatch(failed.session_id)
    running_task = next(task for task in failed.plan.tasks if task.status.value == "running")
    failed = orchestrator_service.complete_delegate(
        OrchestratorDelegateCompletionPayload(
            session_id=failed.session_id,
            task_id=running_task.task_id,
            delegate_run_id=running_task.delegate_run_id or "",
            result=OrchestratorDelegateResult(
                status="failed",
                summary="分析失败",
                changed_files=[],
                error="delegate failed",
            ),
        )
    )

    pending = orchestrator_service.create_session("进入主控，升级项目三", str(third_project))
    pending = orchestrator_service.generate_plan(pending.session_id)
    pending = orchestrator_service.approve_plan(pending.session_id)

    snapshot = orchestrator_service.get_scheduler_snapshot()

    assert snapshot.verification_rollup.total_sessions == 3
    assert snapshot.verification_rollup.passed_sessions == 1
    assert snapshot.verification_rollup.failed_sessions == 1
    assert snapshot.verification_rollup.pending_sessions == 1


def test_resume_session_requeues_failed_task_and_preserves_completed_work(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    session = orchestrator_service.generate_plan(session.session_id)
    session = orchestrator_service.approve_plan(session.session_id)

    session = orchestrator_service.dispatch(session.session_id)
    analyze_task = next(task for task in session.plan.tasks if task.status.value == "running")
    session = orchestrator_service.complete_delegate(
        OrchestratorDelegateCompletionPayload(
            session_id=session.session_id,
            task_id=analyze_task.task_id,
            delegate_run_id=analyze_task.delegate_run_id or "",
            result=OrchestratorDelegateResult(
                status="succeeded",
                summary="分析完成",
                changed_files=[],
            ),
        )
    )

    session = orchestrator_service.dispatch(session.session_id)
    implement_task = next(task for task in session.plan.tasks if task.status.value == "running")
    session = orchestrator_service.complete_delegate(
        OrchestratorDelegateCompletionPayload(
            session_id=session.session_id,
            task_id=implement_task.task_id,
            delegate_run_id=implement_task.delegate_run_id or "",
            result=OrchestratorDelegateResult(
                status="failed",
                summary="实现失败",
                changed_files=[],
                error="delegate failed",
            ),
        )
    )

    resumed = orchestrator_service.resume_session(session.session_id)

    assert resumed.status.value == "dispatching"
    assert resumed.summary == "会话已恢复到主控调度队列。"
    assert resumed.verification is None
    assert resumed.coordination is not None
    assert resumed.coordination.mode.value == "ready"
    assert resumed.plan is not None

    analyze = next(task for task in resumed.plan.tasks if task.task_id == "analyze-1")
    implement = next(task for task in resumed.plan.tasks if task.task_id == "implement-1")
    verify = next(task for task in resumed.plan.tasks if task.task_id == "verify-1")
    summarize = next(task for task in resumed.plan.tasks if task.task_id == "summarize-1")

    assert analyze.status.value == "succeeded"
    assert implement.status.value == "pending"
    assert implement.delegate_run_id is None
    assert implement.error is None
    assert verify.status.value == "pending"
    assert summarize.status.value == "pending"


def test_resume_session_requeues_verification_stage_after_unified_acceptance_failure(project_dir: Path) -> None:
    config = get_runtime_config()
    config.set_folder_permission(str(project_dir), "full_access")
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=InMemoryMemoryRepository(),
    )
    repository = OrchestratorSessionRepository(in_memory=True)

    service = OrchestratorService(
        repository=repository,
        state_store=state_store,
        verification_runner=lambda _path, commands: OrchestratorVerification(
            commands=commands,
            passed=False,
            summary="统一验收失败，需要重跑验收阶段。",
        ),
    )

    session = service.create_session("进入主控，升级当前项目", str(project_dir))
    session = service.generate_plan(session.session_id)
    session = service.approve_plan(session.session_id)

    while session.status.value not in {"completed", "failed"}:
        session = service.dispatch(session.session_id)
        running_task = next(task for task in session.plan.tasks if task.status.value == "running")
        session = service.complete_delegate(
            OrchestratorDelegateCompletionPayload(
                session_id=session.session_id,
                task_id=running_task.task_id,
                delegate_run_id=running_task.delegate_run_id or "",
                result=OrchestratorDelegateResult(
                    status="succeeded",
                    summary=f"{running_task.title} 完成",
                    changed_files=["src/main.ts"] if running_task.kind.value == "implement" else [],
                ),
            )
        )

    assert session.status.value == "failed"
    assert session.verification is not None
    assert session.coordination is not None
    assert session.coordination.failure_category == "verification_failure"

    resumed = service.resume_session(session.session_id)

    assert resumed.status.value == "dispatching"
    assert resumed.verification is None
    assert resumed.plan is not None

    analyze = next(task for task in resumed.plan.tasks if task.task_id == "analyze-1")
    implement = next(task for task in resumed.plan.tasks if task.task_id == "implement-1")
    verify = next(task for task in resumed.plan.tasks if task.task_id == "verify-1")
    summarize = next(task for task in resumed.plan.tasks if task.task_id == "summarize-1")

    assert analyze.status.value == "succeeded"
    assert implement.status.value == "succeeded"
    assert verify.status.value == "pending"
    assert summarize.status.value == "pending"


def test_apply_directive_updates_scope_and_acceptance_commands(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    session = orchestrator_service.generate_plan(session.session_id)

    session = orchestrator_service.apply_directive(session.session_id, "把 scope 限制在 apps/desktop，src-tauri")
    assert session.plan is not None
    analyze = next(task for task in session.plan.tasks if task.task_id == "analyze-1")
    implement = next(task for task in session.plan.tasks if task.task_id == "implement-1")
    assert analyze.scope_paths == ["apps/desktop", "src-tauri"]
    assert implement.scope_paths == ["apps/desktop", "src-tauri"]

    session = orchestrator_service.apply_directive(
        session.session_id,
        "把验收命令改成 cargo test --manifest-path src-tauri/Cargo.toml; npm run build",
    )
    assert session.plan is not None
    implement = next(task for task in session.plan.tasks if task.task_id == "implement-1")
    verify = next(task for task in session.plan.tasks if task.task_id == "verify-1")
    assert implement.acceptance_commands == [
        "cargo test --manifest-path src-tauri/Cargo.toml",
        "npm run build",
    ]
    assert verify.acceptance_commands == [
        "cargo test --manifest-path src-tauri/Cargo.toml",
        "npm run build",
    ]


def test_apply_directive_updates_session_priority_bias(
    orchestrator_service: OrchestratorService,
    project_dir: Path,
) -> None:
    session = orchestrator_service.create_session("进入主控，升级当前项目", str(project_dir))
    raised = orchestrator_service.apply_directive(session.session_id, "把当前会话提到最高优先级")
    assert raised.priority_bias == 80
    assert raised.summary == "当前主控会话已提到最高优先级。"

    reset = orchestrator_service.apply_directive(session.session_id, "恢复普通优先级")
    assert reset.priority_bias == 0
    assert reset.summary == "当前主控会话已恢复普通优先级。"


def test_orchestrator_messages_are_recorded_without_touching_chat_memory(project_dir: Path) -> None:
    config = get_runtime_config()
    config.set_folder_permission(str(project_dir), "full_access")
    memory_repository = InMemoryMemoryRepository()
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=memory_repository,
    )
    conversation_repository = OrchestratorConversationRepository(in_memory=True)
    holder: dict[str, OrchestratorService] = {}
    conversation_service = OrchestratorConversationService(
        repository=conversation_repository,
        scheduler_provider=lambda: holder["service"].get_scheduler_snapshot(),
    )
    service = OrchestratorService(
        repository=OrchestratorSessionRepository(in_memory=True),
        state_store=state_store,
        verification_runner=lambda _path, commands: OrchestratorVerification(commands=commands, passed=True),
        conversation_service=conversation_service,
    )
    holder["service"] = service

    session = service.create_session("进入主控，梳理当前项目", str(project_dir))
    service.generate_plan(session.session_id)

    messages = conversation_repository.list_messages(session.session_id)
    assert len(messages) >= 2
    assert messages[0].role.value == "assistant"
    assert any(block.type == "session_status_card" for block in messages[0].blocks)
    assert any(any(block.type == "plan_card" for block in message.blocks) for message in messages)
    assert memory_repository.list_recent(limit=20) == []


def test_apply_directive_records_directive_card(project_dir: Path) -> None:
    config = get_runtime_config()
    config.set_folder_permission(str(project_dir), "full_access")
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=InMemoryMemoryRepository(),
    )
    conversation_repository = OrchestratorConversationRepository(in_memory=True)
    holder: dict[str, OrchestratorService] = {}
    conversation_service = OrchestratorConversationService(
        repository=conversation_repository,
        scheduler_provider=lambda: holder["service"].get_scheduler_snapshot(),
    )
    service = OrchestratorService(
        repository=OrchestratorSessionRepository(in_memory=True),
        state_store=state_store,
        verification_runner=lambda _path, commands: OrchestratorVerification(commands=commands, passed=True),
        conversation_service=conversation_service,
    )
    holder["service"] = service

    session = service.create_session("进入主控，升级当前项目", str(project_dir))
    session = service.generate_plan(session.session_id)
    service.apply_directive(session.session_id, "把 scope 限制在 apps/desktop")

    messages = conversation_repository.list_messages(session.session_id)
    directive_message = next(
        message
        for message in reversed(messages)
        if any(block.type == "directive_card" for block in message.blocks)
    )
    assert any(block.type == "directive_card" for block in directive_message.blocks)


def test_run_plan_verification_exception_marks_session_failed(project_dir: Path) -> None:
    config = get_runtime_config()
    config.set_folder_permission(str(project_dir), "full_access")
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=InMemoryMemoryRepository(),
    )
    repository = OrchestratorSessionRepository(in_memory=True)

    service = OrchestratorService(
        repository=repository,
        state_store=state_store,
        verification_runner=lambda _path, _commands: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    session = service.create_session("进入主控，升级当前项目", str(project_dir))
    session = service.generate_plan(session.session_id)
    session = service.approve_plan(session.session_id)

    while session.status.value not in {"completed", "failed"}:
        session = service.dispatch(session.session_id)
        running_task = next(task for task in session.plan.tasks if task.status.value == "running")
        session = service.complete_delegate(
            OrchestratorDelegateCompletionPayload(
                session_id=session.session_id,
                task_id=running_task.task_id,
                delegate_run_id=running_task.delegate_run_id or "",
                result=OrchestratorDelegateResult(
                    status="succeeded",
                    summary=f"{running_task.title} 完成",
                    changed_files=["src/main.ts"] if running_task.kind.value == "implement" else [],
                ),
            )
        )

    assert session.status == OrchestratorSessionStatus.FAILED
    assert session.verification is not None
    assert session.verification.passed is False
    assert session.verification.summary is not None
    assert "统一验收执行异常" in session.verification.summary
    assert session.coordination is not None
    assert session.coordination.mode == OrchestratorCoordinationMode.FAILED
    assert session.coordination.failure_category == OrchestratorFailureCategory.VERIFICATION_FAILURE


def test_get_session_auto_recovers_stale_verifying_session(project_dir: Path) -> None:
    config = get_runtime_config()
    config.set_folder_permission(str(project_dir), "full_access")
    state_store = StateStore(
        initial_state=BeingState(mode=WakeMode.AWAKE),
        memory_repository=InMemoryMemoryRepository(),
    )
    repository = OrchestratorSessionRepository(in_memory=True)
    service = OrchestratorService(
        repository=repository,
        state_store=state_store,
        verification_runner=lambda _path, commands: OrchestratorVerification(
            commands=commands,
            passed=True,
            summary=f"验证通过，共执行 {len(commands)} 条命令。",
        ),
    )

    session = service.create_session("进入主控，升级当前项目", str(project_dir))
    session = service.generate_plan(session.session_id)
    session = service.approve_plan(session.session_id)

    while session.status.value != "completed":
        session = service.dispatch(session.session_id)
        running_task = next(task for task in session.plan.tasks if task.status.value == "running")
        session = service.complete_delegate(
            OrchestratorDelegateCompletionPayload(
                session_id=session.session_id,
                task_id=running_task.task_id,
                delegate_run_id=running_task.delegate_run_id or "",
                result=OrchestratorDelegateResult(
                    status="succeeded",
                    summary=f"{running_task.title} 完成",
                    changed_files=["src/main.ts"] if running_task.kind.value == "implement" else [],
                ),
            )
        )

    stale = session.model_copy(
        update={
            "status": OrchestratorSessionStatus.VERIFYING,
            "verification": None,
            "coordination": OrchestratorSessionCoordination(
                mode=OrchestratorCoordinationMode.VERIFYING,
                priority_score=1,
                waiting_reason="正在统一执行计划内验收命令。",
                failure_category=None,
            ),
            "updated_at": datetime.now(timezone.utc) - timedelta(minutes=20),
        }
    )
    repository.save(stale)

    recovered = service.get_session(session.session_id)

    assert recovered.status == OrchestratorSessionStatus.FAILED
    assert recovered.verification is None
    assert recovered.summary is not None
    assert "统一验收状态疑似中断" in recovered.summary
    assert recovered.coordination is not None
    assert recovered.coordination.mode == OrchestratorCoordinationMode.FAILED
    assert recovered.coordination.failure_category == OrchestratorFailureCategory.VERIFICATION_FAILURE

    resumed = service.resume_session(session.session_id)
    assert resumed.status == OrchestratorSessionStatus.DISPATCHING
    assert resumed.verification is None
    assert resumed.plan is not None
    verify = next(task for task in resumed.plan.tasks if task.task_id == "verify-1")
    summarize = next(task for task in resumed.plan.tasks if task.task_id == "summarize-1")
    assert verify.status == "pending"
    assert summarize.status == "pending"
