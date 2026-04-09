from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Callable
from uuid import uuid4

from app.capabilities.models import CapabilityContext, CapabilityDispatchRequest, CapabilityName, RiskLevel
from app.capabilities.runtime import dispatch_and_wait, has_recent_capability_executor
from app.domain.models import (
    DelegateCommandResult,
    FocusMode,
    OrchestratorCoordinationMode,
    OrchestratorDelegateCompletionPayload,
    OrchestratorDelegateRun,
    OrchestratorDelegateResult,
    OrchestratorFailureCategory,
    OrchestratorPlan,
    OrchestratorSchedulerSnapshot,
    OrchestratorSession,
    OrchestratorSessionCoordination,
    OrchestratorSessionStatus,
    OrchestratorTask,
    OrchestratorTaskKind,
    OrchestratorTaskStatus,
    OrchestratorVerification,
    OrchestratorVerificationRollup,
    WakeMode,
)
from app.orchestrator.conversation_service import OrchestratorConversationService
from app.orchestrator.delegate_contract import build_delegate_prompt, build_delegate_request
from app.orchestrator.planner import OrchestratorPlanner
from app.orchestrator.project_context import ProjectContextBuilder
from app.orchestrator.repository import OrchestratorSessionRepository
from app.realtime import AppRealtimeHub
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config

VerificationRunner = Callable[[str, list[str]], OrchestratorVerification]


class OrchestratorService:
    _stuck_verifying_timeout = timedelta(minutes=15)

    def __init__(
        self,
        repository: OrchestratorSessionRepository,
        state_store: StateStore,
        *,
        project_context_builder: ProjectContextBuilder | None = None,
        planner: OrchestratorPlanner | None = None,
        verification_runner: VerificationRunner | None = None,
        max_parallel_sessions: int = 2,
        conversation_service: OrchestratorConversationService | None = None,
    ) -> None:
        self._repository = repository
        self._state_store = state_store
        self._project_context_builder = project_context_builder or ProjectContextBuilder()
        self._planner = planner or OrchestratorPlanner()
        self._verification_runner = verification_runner or self._run_verification_commands
        self._max_parallel_sessions = max(1, max_parallel_sessions)
        self._conversation_service = conversation_service

    def create_session(self, goal: str, project_path: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("goal is required")

        resolved_project_path = self._validate_project_path(project_path)
        session = OrchestratorSession(
            project_path=resolved_project_path,
            project_name=Path(resolved_project_path).name,
            goal=normalized_goal,
            status=OrchestratorSessionStatus.DRAFT,
            coordination=OrchestratorSessionCoordination(
                mode=OrchestratorCoordinationMode.IDLE,
                waiting_reason="等待生成主控计划。",
            ),
            updated_at=self._now(),
        )
        saved = self._repository.save(session)
        self._sync_state(
            saved,
            current_thought=f"已进入主控模式，准备围绕项目 {saved.project_name} 制定执行计划。",
        )
        if self._conversation_service is not None:
            self._conversation_service.append_session_created(saved, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def list_sessions(self) -> list[OrchestratorSession]:
        sessions = self._repository.list_sessions()
        return [self._recover_stuck_verifying_session(session) for session in sessions]

    def activate_session(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        thought = (
            f"已切换主控项目到 {session.project_name}，继续跟进当前编排会话。"
            if session.status not in self._terminal_statuses()
            else f"已切换查看主控会话：{session.project_name}。"
        )
        self._sync_state(session, current_thought=thought)
        self._publish_session_updated(session, hub)
        return session

    def apply_directive(
        self,
        session_id: str,
        message: str,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("directive message is required")

        session = self._get_session(session_id)
        updated = (
            self._apply_scope_directive(session, normalized_message)
            or self._apply_acceptance_directive(session, normalized_message)
            or self._apply_priority_directive(session, normalized_message)
        )
        if updated is None:
            raise ValueError("unsupported orchestrator directive")

        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=f"已接收主控指令：{normalized_message}")
        if self._conversation_service is not None:
            self._conversation_service.append_directive_applied(saved, normalized_message, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def generate_plan(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        snapshot = self._project_context_builder.build(session.project_path)
        plan = self._planner.build_plan(session.goal, snapshot)
        updated = session.model_copy(
            update={
                "plan": plan,
                "status": OrchestratorSessionStatus.PENDING_PLAN_APPROVAL,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.IDLE,
                    waiting_reason="计划已生成，等待计划级审批。",
                ),
                "verification": None,
                "summary": None,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="主控计划已生成，等待计划级审批。")
        if self._conversation_service is not None:
            self._conversation_service.append_plan_generated(saved, hub=hub)
        self._publish_plan_pending(saved, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def approve_plan(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status != OrchestratorSessionStatus.PENDING_PLAN_APPROVAL:
            raise ValueError("session plan is not awaiting approval")

        updated = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.DISPATCHING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.READY,
                    priority_score=self._priority_score(session),
                    waiting_reason="计划已审批，等待调度器分配并行槽。",
                    failure_category=None,
                ),
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="收到计划级审批，开始按依赖关系派发任务。")
        if self._conversation_service is not None:
            self._conversation_service.append_plan_approved(saved, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def reject_plan(
        self,
        session_id: str,
        *,
        reason: str | None = None,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        session = self._get_session(session_id)
        updated = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.DRAFT,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.IDLE,
                    waiting_reason=reason or "计划被拒绝，等待重新规划。",
                ),
                "summary": reason or "计划被拒绝，等待重新规划。",
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=saved.summary or "计划被拒绝，等待重新规划。")
        if self._conversation_service is not None:
            self._conversation_service.append_plan_rejected(saved, reason=reason, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def dispatch(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status not in {OrchestratorSessionStatus.DISPATCHING, OrchestratorSessionStatus.RUNNING}:
            raise ValueError("session is not dispatchable")
        if self._has_running_task(session):
            return session

        next_task = self._find_next_dispatchable_task(session)
        if next_task is None:
            raise ValueError("no dispatchable task available")

        if self._count_running_sessions(exclude_session_id=session.session_id) >= self._max_parallel_sessions:
            waiting = self._mark_session_waiting_for_slot(
                session,
                queue_position=1,
                waiting_reason="并行名额已满，当前不会抢占正在运行的 delegate。",
                preempted_by_session_id=None,
            )
            saved = self._repository.save(waiting)
            self._publish_session_updated(saved, hub)
            return saved

        return self._dispatch_task(session, next_task, hub=hub)

    def run_scheduler_tick(self, *, hub: AppRealtimeHub | None = None) -> OrchestratorSchedulerSnapshot:
        sessions = self._repository.list_sessions()
        active_session_id = self._active_session_id()
        running_sessions = [session for session in sessions if self._has_running_task(session)]
        available_slots = max(0, self._max_parallel_sessions - len(running_sessions))
        dispatchable_sessions = [
            session
            for session in sessions
            if session.status in {OrchestratorSessionStatus.DISPATCHING, OrchestratorSessionStatus.RUNNING}
            and not self._has_running_task(session)
            and self._find_next_dispatchable_task(session) is not None
        ]
        dispatchable_sessions.sort(key=self._dispatch_priority_key)
        selected_ids = {session.session_id for session in dispatchable_sessions[:available_slots]}
        queued_sessions = dispatchable_sessions[available_slots:]

        saved_by_id: dict[str, OrchestratorSession] = {}
        for slot_index, session in enumerate(running_sessions, start=1):
            updated = self._with_coordination(
                session,
                mode=OrchestratorCoordinationMode.RUNNING,
                priority_score=self._priority_score(session),
                dispatch_slot=slot_index,
                queue_position=None,
                waiting_reason="已占用并行槽，等待 delegate 回填。",
                preempted_by_session_id=None,
            )
            saved_by_id[updated.session_id] = self._save_if_changed(updated, hub=hub)

        for queue_index, session in enumerate(queued_sessions, start=1):
            if len(running_sessions) >= self._max_parallel_sessions:
                waiting_reason = "并行名额已满，当前不会抢占正在运行的 delegate。"
                preempted_by = None
            elif active_session_id is not None and active_session_id in selected_ids and session.session_id != active_session_id:
                waiting_reason = "等待并行名额释放，当前优先让活动主控项目先执行。"
                preempted_by = active_session_id
            else:
                waiting_reason = "等待并行名额释放。"
                preempted_by = None
            updated = self._mark_session_waiting_for_slot(
                session,
                queue_position=queue_index,
                waiting_reason=waiting_reason,
                preempted_by_session_id=preempted_by,
            )
            saved_by_id[updated.session_id] = self._save_if_changed(updated, hub=hub)

        for session in dispatchable_sessions[:available_slots]:
            current = saved_by_id.get(session.session_id, session)
            next_dispatchable = self._find_next_dispatchable_task(current)
            if next_dispatchable is None:
                continue
            saved_by_id[session.session_id] = self._dispatch_task(current, next_dispatchable, hub=hub)

        return self.get_scheduler_snapshot()

    def get_scheduler_snapshot(self) -> OrchestratorSchedulerSnapshot:
        sessions = self._repository.list_sessions()
        active_session_id = self._active_session_id()
        running_session_ids = [session.session_id for session in sessions if self._has_running_task(session)]
        queued_session_ids = [
            session.session_id
            for session in sessions
            if session.coordination is not None
            and session.coordination.mode in {OrchestratorCoordinationMode.QUEUED, OrchestratorCoordinationMode.PREEMPTED}
        ]
        passed_sessions = sum(1 for session in sessions if session.verification is not None and session.verification.passed)
        failed_sessions = sum(
            1
            for session in sessions
            if session.status == OrchestratorSessionStatus.FAILED
            or (session.verification is not None and not session.verification.passed)
        )
        pending_sessions = max(0, len(sessions) - passed_sessions - failed_sessions)
        return OrchestratorSchedulerSnapshot(
            max_parallel_sessions=self._max_parallel_sessions,
            running_sessions=len(running_session_ids),
            available_slots=max(0, self._max_parallel_sessions - len(running_session_ids)),
            queued_sessions=len(queued_session_ids),
            active_session_id=active_session_id,
            running_session_ids=running_session_ids,
            queued_session_ids=queued_session_ids,
            verification_rollup=OrchestratorVerificationRollup(
                total_sessions=len(sessions),
                passed_sessions=passed_sessions,
                failed_sessions=failed_sessions,
                pending_sessions=pending_sessions,
            ),
            policy_note=(
                f"最多并行 {self._max_parallel_sessions} 个项目会话；"
                "活动主控项目优先获得下一次派发权；"
                "已经运行中的 delegate 不会被硬中断。"
            ),
        )

    def _dispatch_task(
        self,
        session: OrchestratorSession,
        next_task: OrchestratorTask,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        delegate_run_id = uuid4().hex
        delegate_request = build_delegate_request(goal=session.goal, project_path=session.project_path, task=next_task)
        delegate_prompt = build_delegate_prompt(delegate_request)
        updated_tasks: list[OrchestratorTask] = []
        for task in session.plan.tasks:
            if task.task_id == next_task.task_id:
                updated_tasks.append(
                    task.model_copy(
                        update={
                            "status": OrchestratorTaskStatus.RUNNING,
                            "delegate_run_id": delegate_run_id,
                            "artifacts": {
                                **task.artifacts,
                                "delegate_request": delegate_request.model_dump(mode="json"),
                                "delegate_prompt": delegate_prompt,
                            },
                            "error": None,
                        }
                    )
                )
            else:
                updated_tasks.append(task)

        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        delegates = [
            *session.delegates,
            OrchestratorDelegateRun(
                task_id=next_task.task_id,
                delegate_run_id=delegate_run_id,
                provider=next_task.delegate_target,
            ),
        ]
        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "delegates": delegates,
                "status": OrchestratorSessionStatus.RUNNING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.RUNNING,
                    priority_score=self._priority_score(session),
                    dispatch_slot=1,
                    waiting_reason="已占用并行槽，等待 delegate 回填。",
                    failure_category=None,
                ),
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=f"主控已派发任务：{next_task.title}")
        dispatched_task = self._get_task(saved, next_task.task_id)
        if self._conversation_service is not None:
            self._conversation_service.append_task_update(saved, dispatched_task, phase="任务已派发", hub=hub)
        self._publish_task_updated(saved, dispatched_task, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def get_session(self, session_id: str) -> OrchestratorSession:
        return self._get_session(session_id)

    def list_tasks(self, session_id: str) -> list[OrchestratorTask]:
        session = self._get_session(session_id)
        return [] if session.plan is None else [task.model_copy(deep=True) for task in session.plan.tasks]

    def cancel(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        updated_tasks: list[OrchestratorTask] = []
        if session.plan is not None:
            for task in session.plan.tasks:
                if task.status in {OrchestratorTaskStatus.SUCCEEDED, OrchestratorTaskStatus.FAILED, OrchestratorTaskStatus.CANCELLED}:
                    updated_tasks.append(task)
                else:
                    updated_tasks.append(task.model_copy(update={"status": OrchestratorTaskStatus.CANCELLED}))
        updated_plan = None if session.plan is None else session.plan.model_copy(update={"tasks": updated_tasks})
        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "status": OrchestratorSessionStatus.CANCELLED,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.CANCELLED,
                    waiting_reason="主控会话已取消。",
                    failure_category=None,
                ),
                "summary": session.summary or "主控会话已取消。",
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._clear_state(current_thought="已退出主控模式。")
        if self._conversation_service is not None:
            self._conversation_service.append_session_cancelled(saved, hub=hub)
        self._publish_session_updated(saved, hub)
        return saved

    def resume_session(self, session_id: str, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        session = self._get_session(session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status not in {OrchestratorSessionStatus.FAILED, OrchestratorSessionStatus.CANCELLED}:
            raise ValueError("session is not resumable")

        resumed_plan = self._resume_plan(session)
        if resumed_plan is None:
            raise ValueError("session has no resumable tasks")

        summary = "会话已恢复到主控调度队列。"
        updated = session.model_copy(
            update={
                "plan": resumed_plan,
                "status": OrchestratorSessionStatus.DISPATCHING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.READY,
                    priority_score=self._priority_score(session),
                    waiting_reason=summary,
                    failure_category=None,
                ),
                "verification": None,
                "summary": summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought=summary)
        if self._conversation_service is not None:
            self._conversation_service.append_system_event(
                saved,
                summary=summary,
                blocks=[self._conversation_service.build_session_status_block(saved)],
                hub=hub,
            )
        self._publish_session_updated(saved, hub)
        return saved

    def complete_delegate(
        self,
        payload: OrchestratorDelegateCompletionPayload,
        *,
        hub: AppRealtimeHub | None = None,
    ) -> OrchestratorSession:
        session = self._get_session(payload.session_id)
        if session.plan is None:
            raise ValueError("session plan is not ready")

        task = self._get_task(session, payload.task_id)
        if task.delegate_run_id != payload.delegate_run_id:
            raise ValueError("delegate run id mismatch")

        normalized_changed_files = self._normalize_changed_files(session.project_path, payload.result)
        scope_error = self._validate_changed_files(task, normalized_changed_files)
        final_error = scope_error or payload.result.error
        succeeded = payload.result.status == "succeeded" and final_error is None

        updated_tasks: list[OrchestratorTask] = []
        updated_task: OrchestratorTask | None = None
        for candidate in session.plan.tasks:
            if candidate.task_id == task.task_id:
                updated_task = candidate.model_copy(
                    update={
                        "status": OrchestratorTaskStatus.SUCCEEDED if succeeded else OrchestratorTaskStatus.FAILED,
                        "result_summary": payload.result.summary,
                        "artifacts": {
                            **candidate.artifacts,
                            "delegate_result": payload.result.model_dump(mode="json"),
                            "changed_files": normalized_changed_files,
                        },
                        "error": final_error,
                    }
                )
                updated_tasks.append(updated_task)
            else:
                updated_tasks.append(candidate)

        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        updated_delegates = self._complete_delegate_record(session, task.task_id, payload.delegate_run_id, succeeded)
        updated_status = OrchestratorSessionStatus.DISPATCHING if succeeded else OrchestratorSessionStatus.FAILED
        updated_summary = session.summary
        if not succeeded:
            updated_summary = final_error or payload.result.summary or f"任务失败：{task.title}"

        updated = session.model_copy(
            update={
                "plan": updated_plan,
                "delegates": updated_delegates,
                "status": updated_status,
                "coordination": OrchestratorSessionCoordination(
                    mode=(
                        OrchestratorCoordinationMode.READY
                        if succeeded
                        else OrchestratorCoordinationMode.FAILED
                    ),
                    priority_score=self._priority_score(session),
                    waiting_reason=(
                        "任务已回收，等待下一轮调度。"
                        if succeeded
                        else final_error or payload.result.summary or f"任务失败：{task.title}"
                    ),
                    failure_category=(
                        None
                        if succeeded
                        else self._classify_failure_category(final_error)
                    ),
                ),
                "summary": updated_summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(updated)
        if self._is_active_session(saved.session_id):
            self._sync_state(
                saved,
                current_thought=(
                    f"主控任务失败：{updated_task.title if updated_task is not None else task.title}"
                    if not succeeded
                    else f"任务已回收：{updated_task.title if updated_task is not None else task.title}"
                ),
            )
        if updated_task is not None:
            if self._conversation_service is not None:
                phase = "任务已回收" if succeeded else "任务失败"
                self._conversation_service.append_task_update(saved, updated_task, phase=phase, hub=hub)
            self._publish_task_updated(saved, updated_task, hub)
        self._publish_session_updated(saved, hub)

        if not succeeded:
            return saved

        if self._all_tasks_succeeded(saved):
            return self._run_plan_verification(saved, hub=hub)
        return saved

    def _run_plan_verification(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        commands = self._collect_verification_commands(session)
        verifying = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.VERIFYING,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.VERIFYING,
                    priority_score=self._priority_score(session),
                    waiting_reason="正在统一执行计划内验收命令。",
                    failure_category=None,
                ),
                "updated_at": self._now(),
            }
        )
        verifying = self._repository.save(verifying)
        if self._is_active_session(verifying.session_id):
            self._sync_state(verifying, current_thought="主控正在统一执行计划内验收命令。")
        self._publish_session_updated(verifying, hub)

        try:
            verification = self._verification_runner(verifying.project_path, commands)
        except Exception as error:  # noqa: BLE001 - guard session state from being stuck in verifying forever.
            message = str(error).strip() or error.__class__.__name__
            verification = OrchestratorVerification(
                commands=commands,
                command_results=[],
                passed=False,
                summary=f"统一验收执行异常：{message}",
            )
        completed = verifying.model_copy(
            update={
                "verification": verification,
                "status": OrchestratorSessionStatus.COMPLETED if verification.passed else OrchestratorSessionStatus.FAILED,
                "coordination": OrchestratorSessionCoordination(
                    mode=(
                        OrchestratorCoordinationMode.COMPLETED
                        if verification.passed
                        else OrchestratorCoordinationMode.FAILED
                    ),
                    priority_score=self._priority_score(verifying),
                    waiting_reason=verification.summary,
                    failure_category=(
                        None
                        if verification.passed
                        else OrchestratorFailureCategory.VERIFICATION_FAILURE
                    ),
                ),
                "summary": verification.summary or verifying.summary,
                "updated_at": self._now(),
            }
        )
        saved = self._repository.save(completed)
        if self._is_active_session(saved.session_id):
            self._sync_state(
                saved,
                current_thought=(
                    "主控任务已完成，验证通过。"
                    if verification.passed
                    else "主控任务已回收，但统一验收未通过。"
                ),
            )
        if self._conversation_service is not None:
            self._conversation_service.append_verification_completed(saved, hub=hub)
        self._publish_verification_completed(saved, hub)
        self._publish_session_updated(saved, hub)
        return saved

    def _run_verification_commands(self, project_path: str, commands: list[str]) -> OrchestratorVerification:
        if not commands:
            return OrchestratorVerification(commands=[], command_results=[], passed=True, summary="没有额外验收命令，按计划完成。")

        if not has_recent_capability_executor("desktop", max_age_seconds=30):
            return OrchestratorVerification(
                commands=commands,
                command_results=[],
                passed=False,
                summary="未检测到可用的 desktop capability executor，无法执行统一验收。",
            )

        config = get_runtime_config()
        shell_policy = config.get_capability_shell_policy()
        command_results: list[DelegateCommandResult] = []
        all_passed = True

        for command in commands:
            result = dispatch_and_wait(
                CapabilityDispatchRequest(
                    capability=CapabilityName.SHELL_RUN,
                    args={
                        "command": command,
                        "cwd": project_path,
                        "timeout_seconds": 180,
                        "allowed_executables": list(shell_policy["allowed_executables"]),
                        "allowed_git_subcommands": list(shell_policy["allowed_git_subcommands"]),
                    },
                    risk_level=RiskLevel.RESTRICTED,
                    requires_approval=False,
                    context=CapabilityContext(reason="orchestrator verification"),
                ),
                timeout_seconds=185,
                poll_interval_seconds=0.1,
            )
            if result is None:
                command_results.append(
                    DelegateCommandResult(
                        command=command,
                        success=False,
                        exit_code=None,
                        stderr="capability dispatch timeout",
                    )
                )
                all_passed = False
                continue

            output = result.output if isinstance(result.output, dict) else {}
            shell_success = bool(output.get("success", result.ok))
            command_results.append(
                DelegateCommandResult(
                    command=command,
                    success=shell_success,
                    exit_code=output.get("exit_code") if isinstance(output.get("exit_code"), int) else None,
                    stdout=output.get("stdout") if isinstance(output.get("stdout"), str) else None,
                    stderr=(
                        output.get("stderr") if isinstance(output.get("stderr"), str) else result.error_message
                    ),
                    duration_ms=output.get("duration_ms") if isinstance(output.get("duration_ms"), int) else None,
                )
            )
            if not shell_success:
                all_passed = False

        passed_count = sum(1 for item in command_results if item.success)
        return OrchestratorVerification(
            commands=commands,
            command_results=command_results,
            passed=all_passed,
            summary=f"统一验收执行 {len(commands)} 条命令，通过 {passed_count} 条。",
        )

    def _sync_state(self, session: OrchestratorSession, *, current_thought: str) -> None:
        state = self._state_store.get()
        focus_mode = FocusMode.ORCHESTRATOR
        next_state = state.model_copy(
            update={
                "focus_mode": focus_mode,
                "orchestrator_session": session,
                "current_thought": current_thought,
            }
        )
        self._state_store.set(next_state)

    def _clear_state(self, *, current_thought: str) -> None:
        state = self._state_store.get()
        next_focus_mode = FocusMode.AUTONOMY if state.mode == WakeMode.AWAKE else FocusMode.SLEEPING
        next_state = state.model_copy(
            update={
                "focus_mode": next_focus_mode,
                "orchestrator_session": None,
                "current_thought": current_thought,
            }
        )
        self._state_store.set(next_state)

    def _find_next_dispatchable_task(self, session: OrchestratorSession) -> OrchestratorTask | None:
        if session.plan is None:
            return None
        succeeded = {task.task_id for task in session.plan.tasks if task.status == OrchestratorTaskStatus.SUCCEEDED}
        for task in session.plan.tasks:
            if task.status not in {OrchestratorTaskStatus.PENDING, OrchestratorTaskStatus.QUEUED}:
                continue
            if all(dep in succeeded for dep in task.depends_on):
                return task
        return None

    def _resume_plan(self, session: OrchestratorSession) -> OrchestratorPlan | None:
        if session.plan is None:
            return None

        should_reset_verify_stage = (
            (session.verification is not None and not session.verification.passed)
            or (
                session.status == OrchestratorSessionStatus.FAILED
                and session.coordination is not None
                and session.coordination.failure_category == OrchestratorFailureCategory.VERIFICATION_FAILURE
            )
            or (
                session.status == OrchestratorSessionStatus.FAILED
                and session.verification is None
                and self._all_tasks_succeeded(session)
            )
        )
        updated_tasks: list[OrchestratorTask] = []
        reset_count = 0

        for task in session.plan.tasks:
            should_reset = False
            if should_reset_verify_stage:
                should_reset = task.kind in {OrchestratorTaskKind.VERIFY, OrchestratorTaskKind.SUMMARIZE}
            else:
                should_reset = task.status != OrchestratorTaskStatus.SUCCEEDED

            if should_reset:
                updated_tasks.append(self._reset_task_for_resume(task))
                reset_count += 1
            else:
                updated_tasks.append(task.model_copy(deep=True))

        if reset_count == 0:
            return None
        return session.plan.model_copy(update={"tasks": updated_tasks})

    def _reset_task_for_resume(self, task: OrchestratorTask) -> OrchestratorTask:
        artifacts = dict(task.artifacts)
        for key in ["delegate_request", "delegate_prompt", "delegate_result", "changed_files"]:
            artifacts.pop(key, None)
        return task.model_copy(
            update={
                "status": OrchestratorTaskStatus.PENDING,
                "result_summary": None,
                "artifacts": artifacts,
                "delegate_run_id": None,
                "error": None,
            }
        )

    def _classify_failure_category(self, error: str | None) -> OrchestratorFailureCategory:
        if error and "outside approved scope" in error:
            return OrchestratorFailureCategory.POLICY_VIOLATION
        if error and "forbidden path" in error:
            return OrchestratorFailureCategory.POLICY_VIOLATION
        return OrchestratorFailureCategory.DELEGATE_FAILURE

    def _has_running_task(self, session: OrchestratorSession) -> bool:
        return session.plan is not None and any(task.status == OrchestratorTaskStatus.RUNNING for task in session.plan.tasks)

    def _count_running_sessions(self, *, exclude_session_id: str | None = None) -> int:
        count = 0
        for session in self._repository.list_sessions():
            if exclude_session_id is not None and session.session_id == exclude_session_id:
                continue
            if self._has_running_task(session):
                count += 1
        return count

    def _priority_score(self, session: OrchestratorSession) -> int:
        score = len(session.plan.tasks) if session.plan is not None else 0
        if self._is_active_session(session.session_id):
            score += 100
        if session.status == OrchestratorSessionStatus.RUNNING:
            score += 20
        if session.plan is not None:
            score += sum(10 for task in session.plan.tasks if task.status == OrchestratorTaskStatus.SUCCEEDED)
        score += session.priority_bias
        return score

    def _dispatch_priority_key(self, session: OrchestratorSession) -> tuple[int, float]:
        return (-self._priority_score(session), session.entered_at.timestamp())

    def _mark_session_waiting_for_slot(
        self,
        session: OrchestratorSession,
        *,
        queue_position: int,
        waiting_reason: str,
        preempted_by_session_id: str | None,
    ) -> OrchestratorSession:
        next_task = self._find_next_dispatchable_task(session)
        updated_plan = session.plan
        if session.plan is not None and next_task is not None:
            updated_tasks: list[OrchestratorTask] = []
            for task in session.plan.tasks:
                if task.task_id == next_task.task_id and task.status in {OrchestratorTaskStatus.PENDING, OrchestratorTaskStatus.QUEUED}:
                    updated_tasks.append(task.model_copy(update={"status": OrchestratorTaskStatus.QUEUED}))
                else:
                    updated_tasks.append(task)
            updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})

        mode = (
            OrchestratorCoordinationMode.PREEMPTED
            if preempted_by_session_id is not None
            else OrchestratorCoordinationMode.QUEUED
        )
        return session.model_copy(
            update={
                "plan": updated_plan,
                "coordination": OrchestratorSessionCoordination(
                    mode=mode,
                    priority_score=self._priority_score(session),
                    queue_position=queue_position,
                waiting_reason=waiting_reason,
                failure_category=None,
                preempted_by_session_id=preempted_by_session_id,
            ),
            "updated_at": self._now(),
        }
        )

    def _with_coordination(
        self,
        session: OrchestratorSession,
        *,
        mode: OrchestratorCoordinationMode,
        priority_score: int,
        dispatch_slot: int | None = None,
        queue_position: int | None = None,
        waiting_reason: str | None = None,
        preempted_by_session_id: str | None = None,
    ) -> OrchestratorSession:
        return session.model_copy(
            update={
                "coordination": OrchestratorSessionCoordination(
                    mode=mode,
                    priority_score=priority_score,
                    dispatch_slot=dispatch_slot,
                    queue_position=queue_position,
                    waiting_reason=waiting_reason,
                    failure_category=None,
                    preempted_by_session_id=preempted_by_session_id,
                ),
                "updated_at": self._now(),
            }
        )

    def _save_if_changed(self, session: OrchestratorSession, *, hub: AppRealtimeHub | None = None) -> OrchestratorSession:
        current = self._repository.get(session.session_id)
        if current is not None and current.model_dump(mode="json") == session.model_dump(mode="json"):
            return current
        saved = self._repository.save(session)
        self._publish_session_updated(saved, hub)
        return saved

    def _collect_verification_commands(self, session: OrchestratorSession) -> list[str]:
        if session.plan is None:
            return []
        commands: list[str] = []
        seen: set[str] = set()
        for task in session.plan.tasks:
            for command in task.acceptance_commands:
                normalized = command.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                commands.append(normalized)
        return commands

    def _normalize_changed_files(self, project_path: str, result: OrchestratorDelegateResult) -> list[str]:
        project_root = Path(project_path).resolve()
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_path in result.changed_files:
            candidate = Path(raw_path)
            if candidate.is_absolute():
                try:
                    rel = candidate.resolve().relative_to(project_root)
                    value = rel.as_posix()
                except ValueError:
                    value = candidate.as_posix()
            else:
                value = candidate.as_posix().lstrip("./")
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    def _validate_changed_files(self, task: OrchestratorTask, changed_files: list[str]) -> str | None:
        if not changed_files:
            return None

        forbidden_paths = {".git", ".data", "node_modules", "dist", "build", "target"}
        scope_paths = [item.strip().strip("/") for item in task.scope_paths if item.strip()]
        if not scope_paths or "." in scope_paths:
            scope_paths = ["."]

        for changed_file in changed_files:
            normalized = changed_file.strip().strip("/")
            if not normalized:
                continue
            if any(normalized == forbidden or normalized.startswith(f"{forbidden}/") for forbidden in forbidden_paths):
                return f"delegate changed forbidden path: {changed_file}"
            if scope_paths == ["."]:
                continue
            if not any(normalized == scope or normalized.startswith(f"{scope}/") for scope in scope_paths):
                return f"delegate changed file outside approved scope: {changed_file}"
        return None

    def _complete_delegate_record(
        self,
        session: OrchestratorSession,
        task_id: str,
        delegate_run_id: str,
        succeeded: bool,
    ) -> list[OrchestratorDelegateRun]:
        completed: list[OrchestratorDelegateRun] = []
        for item in session.delegates:
            if item.task_id == task_id and item.delegate_run_id == delegate_run_id:
                completed.append(
                    item.model_copy(
                        update={
                            "status": "succeeded" if succeeded else "failed",
                            "completed_at": self._now(),
                        }
                    )
                )
            else:
                completed.append(item)
        return completed

    def _all_tasks_succeeded(self, session: OrchestratorSession) -> bool:
        return session.plan is not None and all(task.status == OrchestratorTaskStatus.SUCCEEDED for task in session.plan.tasks)

    def _get_session(self, session_id: str) -> OrchestratorSession:
        session = self._repository.get(session_id)
        if session is None:
            raise ValueError("orchestrator session not found")
        return self._recover_stuck_verifying_session(session)

    def _recover_stuck_verifying_session(self, session: OrchestratorSession) -> OrchestratorSession:
        if session.status != OrchestratorSessionStatus.VERIFYING:
            return session
        if session.verification is not None:
            return session
        if not self._all_tasks_succeeded(session):
            return session

        now = self._now()
        if now - session.updated_at < self._stuck_verifying_timeout:
            return session

        summary = "统一验收状态疑似中断（超过 15 分钟无更新），已自动标记为失败，请恢复推进重跑验收。"
        recovered = session.model_copy(
            update={
                "status": OrchestratorSessionStatus.FAILED,
                "coordination": OrchestratorSessionCoordination(
                    mode=OrchestratorCoordinationMode.FAILED,
                    priority_score=self._priority_score(session),
                    waiting_reason=summary,
                    failure_category=OrchestratorFailureCategory.VERIFICATION_FAILURE,
                ),
                "summary": summary,
                "updated_at": now,
            }
        )
        saved = self._repository.save(recovered)
        if self._is_active_session(saved.session_id):
            self._sync_state(saved, current_thought="主控统一验收疑似中断，已自动标记为失败，等待恢复。")
        if self._conversation_service is not None:
            self._conversation_service.append_system_event(
                saved,
                summary=summary,
                blocks=[self._conversation_service.build_session_status_block(saved)],
            )
        return saved

    def _get_task(self, session: OrchestratorSession, task_id: str) -> OrchestratorTask:
        if session.plan is None:
            raise ValueError("session plan is not ready")
        for task in session.plan.tasks:
            if task.task_id == task_id:
                return task
        raise ValueError("orchestrator task not found")

    def _validate_project_path(self, project_path: str) -> str:
        resolved = str(Path(project_path).expanduser().resolve())
        permissions = get_runtime_config().list_folder_permissions()
        if not permissions:
            raise ValueError("no imported project is available for orchestrator mode")
        for granted_path, access_level in permissions:
            if str(Path(granted_path).expanduser().resolve()) == resolved:
                return resolved
        raise ValueError("project_path is not part of the imported project registry")

    def _is_active_session(self, session_id: str) -> bool:
        current = self._state_store.get().orchestrator_session
        return current is not None and current.session_id == session_id

    def _active_session_id(self) -> str | None:
        current = self._state_store.get().orchestrator_session
        return None if current is None else current.session_id

    def _publish_session_updated(self, session: OrchestratorSession, hub: AppRealtimeHub | None) -> None:
        if hub is not None:
            hub.publish_orchestrator_session_updated(session.model_dump(mode="json"))

    def _publish_task_updated(
        self,
        session: OrchestratorSession,
        task: OrchestratorTask,
        hub: AppRealtimeHub | None,
    ) -> None:
        if hub is not None:
            hub.publish_orchestrator_task_updated(
                {
                    "session_id": session.session_id,
                    "task": task.model_dump(mode="json"),
                }
            )

    def _publish_plan_pending(self, session: OrchestratorSession, hub: AppRealtimeHub | None) -> None:
        if hub is not None and session.plan is not None:
            hub.publish_orchestrator_plan_pending_approval(
                {
                    "session_id": session.session_id,
                    "plan": session.plan.model_dump(mode="json"),
                }
            )

    def _publish_verification_completed(self, session: OrchestratorSession, hub: AppRealtimeHub | None) -> None:
        if hub is not None and session.verification is not None:
            hub.publish_orchestrator_verification_completed(
                {
                    "session_id": session.session_id,
                    "verification": session.verification.model_dump(mode="json"),
                    "status": session.status.value,
                }
            )

    def _terminal_statuses(self) -> set[OrchestratorSessionStatus]:
        return {
            OrchestratorSessionStatus.COMPLETED,
            OrchestratorSessionStatus.FAILED,
            OrchestratorSessionStatus.CANCELLED,
        }

    def _apply_scope_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        paths = self._extract_scope_paths(message)
        if paths is None:
            return None
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if any(
            task.status == OrchestratorTaskStatus.RUNNING
            and task.kind in {OrchestratorTaskKind.ANALYZE, OrchestratorTaskKind.IMPLEMENT}
            for task in session.plan.tasks
        ):
            raise ValueError("cannot change scope while analyze/implement delegate is running")

        updated_tasks: list[OrchestratorTask] = []
        changed = False
        for task in session.plan.tasks:
            if task.kind in {OrchestratorTaskKind.ANALYZE, OrchestratorTaskKind.IMPLEMENT} and task.status != OrchestratorTaskStatus.SUCCEEDED:
                next_task = task.model_copy(update={"scope_paths": paths})
                updated_tasks.append(next_task)
                changed = changed or next_task.scope_paths != task.scope_paths
            else:
                updated_tasks.append(task.model_copy(deep=True))

        if not changed:
            raise ValueError("scope_paths already match the requested directive")

        summary = f"主控边界已更新，后续分析/实现仅允许作用于：{', '.join(paths)}"
        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        return session.model_copy(
            update={
                "plan": updated_plan,
                "summary": summary,
                "coordination": self._copy_coordination(session, priority_score=self._priority_score(session)),
                "updated_at": self._now(),
            }
        )

    def _apply_acceptance_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        commands = self._extract_acceptance_commands(message)
        if commands is None:
            return None
        if session.plan is None:
            raise ValueError("session plan is not ready")
        if session.status == OrchestratorSessionStatus.VERIFYING or any(
            task.status == OrchestratorTaskStatus.RUNNING
            and task.kind in {OrchestratorTaskKind.VERIFY, OrchestratorTaskKind.SUMMARIZE}
            for task in session.plan.tasks
        ):
            raise ValueError("cannot change acceptance commands while verification is running")

        updated_tasks: list[OrchestratorTask] = []
        changed = False
        for task in session.plan.tasks:
            if task.kind in {OrchestratorTaskKind.IMPLEMENT, OrchestratorTaskKind.VERIFY} and task.status != OrchestratorTaskStatus.SUCCEEDED:
                next_task = task.model_copy(update={"acceptance_commands": commands})
                updated_tasks.append(next_task)
                changed = changed or next_task.acceptance_commands != task.acceptance_commands
            else:
                updated_tasks.append(task.model_copy(deep=True))

        if not changed:
            raise ValueError("acceptance commands already match the requested directive")

        summary = f"计划内验收命令已更新为：{' | '.join(commands)}"
        updated_plan = session.plan.model_copy(update={"tasks": updated_tasks})
        return session.model_copy(
            update={
                "plan": updated_plan,
                "verification": None,
                "summary": summary,
                "coordination": self._copy_coordination(session, priority_score=self._priority_score(session)),
                "updated_at": self._now(),
            }
        )

    def _apply_priority_directive(
        self,
        session: OrchestratorSession,
        message: str,
    ) -> OrchestratorSession | None:
        normalized = message.strip()
        priority_bias: int | None = None
        summary: str | None = None

        if re.search(r"(提到最高|最高优先级|优先级最高|加急)", normalized):
            priority_bias = 80
            summary = "当前主控会话已提到最高优先级。"
        elif re.search(r"(降低优先级|低优先级|延后处理)", normalized):
            priority_bias = -40
            summary = "当前主控会话已降为低优先级。"
        elif re.search(r"(恢复普通优先级|普通优先级|默认优先级)", normalized):
            priority_bias = 0
            summary = "当前主控会话已恢复普通优先级。"

        if priority_bias is None or summary is None:
            return None
        if session.priority_bias == priority_bias:
            raise ValueError("session priority already matches the requested directive")

        updated = session.model_copy(
            update={
                "priority_bias": priority_bias,
                "summary": summary,
                "updated_at": self._now(),
            }
        )
        return updated.model_copy(
            update={
                "coordination": self._copy_coordination(updated, priority_score=self._priority_score(updated)),
            }
        )

    def _copy_coordination(
        self,
        session: OrchestratorSession,
        *,
        priority_score: int,
    ) -> OrchestratorSessionCoordination:
        if session.coordination is None:
            return OrchestratorSessionCoordination(
                mode=OrchestratorCoordinationMode.IDLE,
                priority_score=priority_score,
                waiting_reason=session.summary,
                failure_category=None,
            )
        return session.coordination.model_copy(update={"priority_score": priority_score})

    def _extract_scope_paths(self, message: str) -> list[str] | None:
        patterns = [
            r"(?:scope|范围|改动范围).{0,12}(?:限制在|限定到|改成|设为)\s*(.+)$",
            r"(?:只允许改|只改|限定在|限定到)\s*(.+)$",
        ]
        raw_value: str | None = None
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                break
        if raw_value is None:
            return None

        parts = re.split(r"[，,、\n]|(?:\s+和\s+)", raw_value)
        normalized: list[str] = []
        for part in parts:
            item = part.strip().strip("\"'`")
            if not item:
                continue
            if item in {"当前项目", "项目根", "根目录"}:
                item = "."
            item = item.replace("\\", "/").lstrip("./").rstrip("/")
            normalized.append(item or ".")
        deduped = list(dict.fromkeys(normalized))
        return deduped or None

    def _extract_acceptance_commands(self, message: str) -> list[str] | None:
        patterns = [
            r"(?:验收命令|测试命令|验证命令).{0,8}(?:改成|换成|设为|只跑|变更为)\s*(.+)$",
        ]
        raw_value: str | None = None
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                break
        if raw_value is None:
            return None

        commands = [
            item.strip()
            for item in re.split(r"[；;\n]+", raw_value)
            if item.strip()
        ]
        return list(dict.fromkeys(commands)) or None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
