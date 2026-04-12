from fastapi.testclient import TestClient

from app.main import (
    app,
    get_chat_gateway,
    get_orchestrator_conversation_service,
    get_orchestrator_service,
)
from app.domain.models import (
    OrchestratorCoordinationMode,
    OrchestratorPlan,
    OrchestratorSchedulerSnapshot,
    OrchestratorSession,
    OrchestratorSessionCoordination,
    OrchestratorSessionStatus,
    OrchestratorTask,
    OrchestratorTaskKind,
    OrchestratorTaskStallFollowup,
    OrchestratorTaskStatus,
    OrchestratorVerificationRollup,
    ProjectSnapshot,
)
from app.orchestrator.conversation_models import OrchestratorChatSubmissionResult


class StubOrchestratorService:
    def __init__(self, session: OrchestratorSession) -> None:
        self.session = session
        self.create_calls = 0
        self.generate_plan_calls = 0
        self.apply_directive_calls = 0
        self.resume_calls = 0
        self.approve_calls = 0
        self.reject_calls = 0
        self.run_scheduler_tick_calls = 0

    def get_session(self, session_id: str) -> OrchestratorSession:
        assert session_id == self.session.session_id
        return self.session

    def list_tasks(self, session_id: str) -> list[OrchestratorTask]:
        assert session_id == self.session.session_id
        if self.session.plan is None:
            return []
        return [task.model_copy(deep=True) for task in self.session.plan.tasks]

    def delete_session(self, session_id: str, *, hub=None) -> int:
        _ = hub
        assert session_id == self.session.session_id
        return 0

    def create_session(self, goal: str, project_path: str, *, hub=None) -> OrchestratorSession:
        _ = hub
        self.create_calls += 1
        self.session = self.session.model_copy(
            update={
                "goal": goal,
                "project_path": project_path,
                "project_name": project_path.rsplit("/", 1)[-1] or project_path,
                "status": OrchestratorSessionStatus.DRAFT,
            }
        )
        return self.session

    def generate_plan(self, session_id: str, *, hub=None) -> OrchestratorSession:
        _ = hub
        assert session_id == self.session.session_id
        self.generate_plan_calls += 1
        self.session = self.session.model_copy(update={"status": OrchestratorSessionStatus.PENDING_PLAN_APPROVAL})
        return self.session

    def apply_directive(self, session_id: str, message: str, *, hub=None) -> OrchestratorSession:
        _ = (session_id, message, hub)
        self.apply_directive_calls += 1
        raise ValueError("unsupported orchestrator directive")

    def resume_session(self, session_id: str, *, hub=None) -> OrchestratorSession:
        _ = (session_id, hub)
        self.resume_calls += 1
        self.session = self.session.model_copy(update={"status": OrchestratorSessionStatus.DISPATCHING})
        return self.session

    def approve_plan(self, session_id: str, *, hub=None) -> OrchestratorSession:
        _ = (session_id, hub)
        self.approve_calls += 1
        self.session = self.session.model_copy(update={"status": OrchestratorSessionStatus.DISPATCHING})
        return self.session

    def reject_plan(self, session_id: str, *, reason: str | None = None, hub=None) -> OrchestratorSession:
        _ = (session_id, reason, hub)
        self.reject_calls += 1
        self.session = self.session.model_copy(update={"status": OrchestratorSessionStatus.DRAFT})
        return self.session

    def run_scheduler_tick(self, *, hub=None) -> OrchestratorSchedulerSnapshot:
        _ = hub
        self.run_scheduler_tick_calls += 1
        return OrchestratorSchedulerSnapshot(
            max_parallel_sessions=2,
            running_sessions=0,
            available_slots=2,
            queued_sessions=0,
            running_session_ids=[],
            queued_session_ids=[],
            verification_rollup=OrchestratorVerificationRollup(),
        )


class StubOrchestratorConversationService:
    def __init__(self) -> None:
        self.user_messages: list[str] = []
        self.stream_calls = 0
        self.stream_user_messages: list[str] = []
        self.system_events: list[tuple[str, object | None]] = []
        self.cleared_session_ids: list[str] = []

    def append_user_message(self, session_id: str, message: str, *, hub=None):
        _ = (session_id, hub)
        self.user_messages.append(message)

    def stream_assistant_reply(self, session: OrchestratorSession, user_message: str, *, gateway, hub=None):
        _ = (gateway, hub, user_message)
        self.stream_calls += 1
        self.stream_user_messages.append(user_message)
        return OrchestratorChatSubmissionResult(
            session_id=session.session_id,
            assistant_message_id="assistant_test_1",
        )

    def append_assistant_message(self, session: OrchestratorSession, reply: str, *, blocks=None, hub=None):
        _ = (session, reply, blocks, hub)
        raise AssertionError("append_assistant_message should not be called in fallback path")

    def append_system_event(
        self,
        session: OrchestratorSession,
        *,
        summary: str,
        blocks=None,
        related_task_id: str | None = None,
        hub=None,
    ):
        _ = (session, related_task_id, hub)
        self.system_events.append((summary, blocks))

        class _Message:
            message_id = "system_event_test_1"

        return _Message()

    def clear_messages(self, session_id: str) -> int:
        self.cleared_session_ids.append(session_id)
        return 2


def test_orchestrator_chat_falls_back_when_directive_is_unsupported() -> None:
    session = OrchestratorSession(
        session_id="session_chat_fallback",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "这个范围先不用改，先解释当前进度"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_test_1",
        }
        assert service.apply_directive_calls == 1
        assert conversation_service.stream_calls == 1
        assert conversation_service.stream_user_messages == ["这个范围先不用改，先解释当前进度"]
        assert conversation_service.system_events == []
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_chat_continue_alias_maps_to_contextual_command() -> None:
    session = OrchestratorSession(
        session_id="session_chat_continue_alias",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.RUNNING,
        plan=OrchestratorPlan(
            objective="处理当前项目",
            project_snapshot=ProjectSnapshot(
                project_path="/tmp/demo",
                project_name="demo",
                repository_root="/tmp/demo",
            ),
            tasks=[
                OrchestratorTask(
                    task_id="task-running-1",
                    title="修复主控输入",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    status=OrchestratorTaskStatus.RUNNING,
                )
            ],
        ),
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "继续推进"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_test_1",
        }
        assert service.apply_directive_calls == 1
        assert service.resume_calls == 0
        assert conversation_service.stream_calls == 1
        assert conversation_service.stream_user_messages == ["解释一下任务「修复主控输入」现在推进到哪一步"]
        assert conversation_service.system_events
        assert conversation_service.system_events[0][0] == "已按当前主控状态执行为：解释一下任务「修复主控输入」现在推进到哪一步"
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_chat_continue_alias_prioritizes_engineer_followup_when_task_is_stalled() -> None:
    session = OrchestratorSession(
        session_id="session_chat_continue_stalled_task",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.RUNNING,
        plan=OrchestratorPlan(
            objective="处理当前项目",
            project_snapshot=ProjectSnapshot(
                project_path="/tmp/demo",
                project_name="demo",
                repository_root="/tmp/demo",
            ),
            tasks=[
                OrchestratorTask(
                    task_id="task-running-1",
                    title="修复主控输入",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    status=OrchestratorTaskStatus.RUNNING,
                    engineer_id=1,
                    engineer_label="工程师1号(codex)",
                    stall_level="hard_intervention",
                    stall_followup=OrchestratorTaskStallFollowup(level="hard_intervention"),
                )
            ],
        ),
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "继续推进"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_test_1",
        }
        assert service.apply_directive_calls == 1
        assert service.resume_calls == 0
        assert conversation_service.stream_calls == 1
        assert conversation_service.stream_user_messages == ["追问工程师1号(codex)卡点并给建议"]
        assert conversation_service.system_events
        assert conversation_service.system_events[0][0] == "已按当前主控状态执行为：追问工程师1号(codex)卡点并给建议"
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_chat_continue_alias_for_pending_task_does_not_misroute_to_resume() -> None:
    session = OrchestratorSession(
        session_id="session_chat_continue_pending_task",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.DISPATCHING,
        plan=OrchestratorPlan(
            objective="处理当前项目",
            project_snapshot=ProjectSnapshot(
                project_path="/tmp/demo",
                project_name="demo",
                repository_root="/tmp/demo",
            ),
            tasks=[
                OrchestratorTask(
                    task_id="task-pending-1",
                    title="修复主控输入",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    status=OrchestratorTaskStatus.PENDING,
                )
            ],
        ),
    )

    class StubServiceNoResume(StubOrchestratorService):
        def resume_session(self, session_id: str, *, hub=None) -> OrchestratorSession:
            _ = (session_id, hub)
            self.resume_calls += 1
            raise ValueError("session is not resumable")

    service = StubServiceNoResume(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "继续推进"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_test_1",
        }
        assert service.resume_calls == 0
        assert service.apply_directive_calls == 1
        assert conversation_service.stream_calls == 1
        assert conversation_service.stream_user_messages == ["继续推进任务「修复主控输入」，并告诉我你准备怎么做"]
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_chat_continue_alias_can_auto_apply_pending_approval_action() -> None:
    session = OrchestratorSession(
        session_id="session_chat_continue_pending_approval",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.PENDING_PLAN_APPROVAL,
    )

    class StubConversationForMappedHandled(StubOrchestratorConversationService):
        def __init__(self) -> None:
            super().__init__()
            self.assistant_replies: list[str] = []

        def append_assistant_message(self, session: OrchestratorSession, reply: str, *, blocks=None, hub=None):
            _ = (session, blocks, hub)
            self.assistant_replies.append(reply)

            class _Message:
                message_id = "assistant_mapped_handled_1"

            return _Message()

    service = StubOrchestratorService(session)
    conversation_service = StubConversationForMappedHandled()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "继续推进"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_mapped_handled_1",
        }
        assert service.approve_calls == 1
        assert service.resume_calls == 0
        assert conversation_service.stream_calls == 0
        assert conversation_service.assistant_replies == [
            "已按当前主控状态执行为：批准计划并开工\n\n好的，计划已批准，我会开始推进当前主控任务。"
        ]
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_chat_can_assign_task_via_directive() -> None:
    session = OrchestratorSession(
        session_id="session_chat_assign",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )

    class StubDirectiveService(StubOrchestratorService):
        def apply_directive(self, session_id: str, message: str, *, hub=None) -> OrchestratorSession:
            _ = (session_id, hub)
            self.apply_directive_calls += 1
            if "指派任务" not in message and "任务:" not in message:
                raise ValueError("unsupported orchestrator directive")
            self.session = self.session.model_copy(
                update={
                    "status": OrchestratorSessionStatus.DISPATCHING,
                    "summary": "已新增聊天任务（ID: chat-implement-1），准备交给 Codex：修复主控输入",
                    "coordination": OrchestratorSessionCoordination(
                        mode=OrchestratorCoordinationMode.READY,
                        priority_score=100,
                        waiting_reason="已新增聊天任务，等待调度器派发。",
                    ),
                    "plan": OrchestratorPlan(
                        objective=self.session.goal,
                        project_snapshot=ProjectSnapshot(
                            project_path=self.session.project_path,
                            project_name=self.session.project_name,
                            repository_root=self.session.project_path,
                        ),
                        tasks=[
                            OrchestratorTask(
                                task_id="chat-implement-1",
                                title="聊天指派：修复主控输入",
                                kind=OrchestratorTaskKind.IMPLEMENT,
                                status=OrchestratorTaskStatus.PENDING,
                                assignment_source="chat_assignment",
                                assignment_directive="指派任务：修复主控输入流程",
                            )
                        ],
                    ),
                }
            )
            return self.session

        def run_scheduler_tick(self, *, hub=None) -> OrchestratorSchedulerSnapshot:
            _ = hub
            self.run_scheduler_tick_calls += 1
            self.session = self.session.model_copy(
                update={
                    "coordination": OrchestratorSessionCoordination(
                        mode=OrchestratorCoordinationMode.QUEUED,
                        priority_score=100,
                        queue_position=2,
                        waiting_reason="等待并行名额释放。",
                    )
                }
            )
            return OrchestratorSchedulerSnapshot(
                max_parallel_sessions=2,
                running_sessions=1,
                available_slots=1,
                queued_sessions=1,
                running_session_ids=["other-session"],
                queued_session_ids=[self.session.session_id],
                verification_rollup=OrchestratorVerificationRollup(),
            )

    class StubDirectiveConversationService(StubOrchestratorConversationService):
        def __init__(self) -> None:
            super().__init__()
            self.assistant_replies: list[str] = []
            self.assistant_blocks: list[object] = []

        def append_assistant_message(self, session: OrchestratorSession, reply: str, *, blocks=None, hub=None):
            _ = (session, hub)
            self.assistant_replies.append(reply)
            if blocks is not None:
                self.assistant_blocks.extend(blocks)

            class _Message:
                message_id = "assistant_assign_task_1"

            return _Message()

    service = StubDirectiveService(session)
    conversation_service = StubDirectiveConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "指派任务：修复主控输入流程"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_assign_task_1",
        }
        assert service.apply_directive_calls == 1
        assert service.run_scheduler_tick_calls == 1
        assert conversation_service.stream_calls == 0
        assert conversation_service.assistant_replies == [
            (
                "已新增聊天任务（ID: chat-implement-1），准备交给 Codex：修复主控输入\n\n"
                "当前排队位次: #2（任务ID: chat-implement-1）\n"
                "下一动作: 等待并行名额释放。\n"
                "建议指令: 继续推进"
            )
        ]
        assert any(
            getattr(block, "type", "") == "next_action_card"
            and getattr(block, "details", {}).get("suggested_command") == "继续推进"
            and getattr(block, "details", {}).get("suggested_commands") == ["继续推进", "先解释当前推进到哪一步"]
            and getattr(block, "details", {}).get("suggestions") == [
                {
                    "command": "继续推进",
                    "priority": "recommended",
                    "reason": "保持调度心跳，名额释放后可立即继续执行。",
                    "confidence": 0.88,
                },
                {
                    "command": "先解释当前推进到哪一步",
                    "priority": "alternative",
                    "reason": "可先获得当前队列状态和预计执行路径。",
                    "confidence": 0.74,
                },
            ]
            for block in conversation_service.assistant_blocks
        )
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_directive_returns_400_when_unsupported() -> None:
    session = OrchestratorSession(
        session_id="session_directive_unsupported",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/directive",
            json={"message": "这个范围先不用改，先解释当前进度"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "unsupported orchestrator directive"
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_messages_can_be_cleared() -> None:
    session = OrchestratorSession(
        session_id="session_clear_messages",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.delete(f"/orchestrator/sessions/{session.session_id}/messages")

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "deleted_count": 2,
        }
        assert conversation_service.cleared_session_ids == [session.session_id]
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_chat_numeric_choice_can_resume_failed_session() -> None:
    session = OrchestratorSession(
        session_id="session_numeric_choice_resume",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.FAILED,
    )
    service = StubOrchestratorService(session)
    class StubConversationForNumericChoice(StubOrchestratorConversationService):
        def append_assistant_message(self, session: OrchestratorSession, reply: str, *, blocks=None, hub=None):
            _ = (session, blocks, hub)
            self.user_messages.append(f"assistant:{reply}")
            class _Message:
                message_id = "assistant_numeric_choice_1"
            return _Message()

    conversation_service = StubConversationForNumericChoice()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            f"/orchestrator/sessions/{session.session_id}/chat",
            json={"message": "2"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "assistant_message_id": "assistant_numeric_choice_1",
        }
        assert service.resume_calls == 1
        assert service.apply_directive_calls == 0
        assert conversation_service.stream_calls == 0
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_console_command_uses_existing_session() -> None:
    session = OrchestratorSession(
        session_id="session_console_existing",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.RUNNING,
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            "/orchestrator/console/command",
            json={
                "session_id": session.session_id,
                "message": "先解释当前推进到哪一步",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["created_session"] is False
        assert payload["assistant_message_id"] == "assistant_test_1"
        assert payload["session"]["session_id"] == session.session_id
        assert service.create_calls == 0
        assert service.generate_plan_calls == 0
        assert service.approve_calls == 0
        assert conversation_service.stream_calls == 1
        assert conversation_service.stream_user_messages == ["先解释当前推进到哪一步"]
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_console_command_creates_session_when_session_id_missing() -> None:
    session = OrchestratorSession(
        session_id="session_console_new",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        status=OrchestratorSessionStatus.DRAFT,
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            "/orchestrator/console/command",
            json={
                "project_path": "/tmp/demo-project",
                "message": "进入主控后先帮我总结当前进展",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["created_session"] is True
        assert payload["assistant_message_id"] == "assistant_test_1"
        assert payload["session"]["session_id"] == session.session_id
        assert service.create_calls == 1
        assert service.generate_plan_calls == 1
        assert service.approve_calls == 1
        assert conversation_service.stream_calls == 1
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_console_command_requires_project_path_when_session_id_missing() -> None:
    session = OrchestratorSession(
        session_id="session_console_new_missing_project",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_chat_gateway] = lambda: object()

    try:
        client = TestClient(app)
        response = client.post(
            "/orchestrator/console/command",
            json={
                "message": "进入主控后先帮我总结当前进展",
            },
        )

        assert response.status_code == 400
        assert "project_path is required" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_list_sessions_passes_filters() -> None:
    session = OrchestratorSession(
        session_id="session_list_filters",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )

    class StubListService(StubOrchestratorService):
        def __init__(self, base_session: OrchestratorSession) -> None:
            super().__init__(base_session)
            self.last_filters: dict[str, object] = {}

        def list_sessions(
            self,
            *,
            statuses=None,
            project=None,
            from_time=None,
            to_time=None,
            keyword=None,
        ):
            self.last_filters = {
                "statuses": statuses,
                "project": project,
                "from_time": from_time,
                "to_time": to_time,
                "keyword": keyword,
            }
            return [self.session]

    service = StubListService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.get(
            "/orchestrator/sessions",
            params={
                "status": "running",
                "project": "demo",
                "from": "2026-04-01T00:00:00Z",
                "to": "2026-04-12T00:00:00Z",
                "keyword": "当前项目",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0]["session_id"] == session.session_id
        assert service.last_filters.get("project") == "demo"
        assert service.last_filters.get("keyword") == "当前项目"
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_get_session_response_exposes_assignment_fields() -> None:
    session = OrchestratorSession(
        session_id="session_get_assignment_fields",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        plan=OrchestratorPlan(
            objective="处理当前项目",
            project_snapshot=ProjectSnapshot(
                project_path="/tmp/demo",
                project_name="demo",
                repository_root="/tmp/demo",
            ),
            tasks=[
                OrchestratorTask(
                    task_id="chat-implement-1",
                    title="聊天指派：修复主控输入",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    status=OrchestratorTaskStatus.PENDING,
                    assignment_source="chat_assignment",
                    assignment_directive="指派任务：修复主控输入流程",
                    assignment_requested_objective="修复主控输入流程",
                    assignment_scope_override=["apps/desktop"],
                    assignment_resolved_scope_override=["apps/desktop", "services/core"],
                    assignment_acceptance_override=["pnpm -C apps/desktop vitest run"],
                    assignment_priority_override=80,
                )
            ],
        ),
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.get(f"/orchestrator/sessions/{session.session_id}")
        assert response.status_code == 200

        tasks = response.json()["plan"]["tasks"]
        assert len(tasks) == 1
        task = tasks[0]
        assert task["assignment_source"] == "chat_assignment"
        assert task["assignment_directive"] == "指派任务：修复主控输入流程"
        assert task["assignment_requested_objective"] == "修复主控输入流程"
        assert task["assignment_scope_override"] == ["apps/desktop"]
        assert task["assignment_resolved_scope_override"] == ["apps/desktop", "services/core"]
        assert task["assignment_acceptance_override"] == ["pnpm -C apps/desktop vitest run"]
        assert task["assignment_priority_override"] == 80
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_list_sessions_response_exposes_assignment_fields() -> None:
    session = OrchestratorSession(
        session_id="session_list_assignment_fields",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        plan=OrchestratorPlan(
            objective="处理当前项目",
            project_snapshot=ProjectSnapshot(
                project_path="/tmp/demo",
                project_name="demo",
                repository_root="/tmp/demo",
            ),
            tasks=[
                OrchestratorTask(
                    task_id="chat-implement-2",
                    title="聊天指派：补齐执行者看板",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    status=OrchestratorTaskStatus.QUEUED,
                    assignment_source="chat_assignment",
                    assignment_directive="任务：补齐执行者看板",
                    assignment_requested_objective="补齐执行者看板",
                    assignment_scope_override=["apps/desktop/src/components/orchestrator"],
                    assignment_resolved_scope_override=["apps/desktop/src/components/orchestrator"],
                    assignment_acceptance_override=["pnpm -C apps/desktop test"],
                    assignment_priority_override=60,
                )
            ],
        ),
    )

    class StubListAssignmentService(StubOrchestratorService):
        def list_sessions(
            self,
            *,
            statuses=None,
            project=None,
            from_time=None,
            to_time=None,
            keyword=None,
        ):
            _ = (statuses, project, from_time, to_time, keyword)
            return [self.session]

    service = StubListAssignmentService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.get("/orchestrator/sessions")
        assert response.status_code == 200

        payload = response.json()
        assert isinstance(payload, list)
        assert len(payload) == 1
        tasks = payload[0]["plan"]["tasks"]
        assert len(tasks) == 1
        task = tasks[0]
        assert task["assignment_source"] == "chat_assignment"
        assert task["assignment_directive"] == "任务：补齐执行者看板"
        assert task["assignment_requested_objective"] == "补齐执行者看板"
        assert task["assignment_scope_override"] == ["apps/desktop/src/components/orchestrator"]
        assert task["assignment_resolved_scope_override"] == ["apps/desktop/src/components/orchestrator"]
        assert task["assignment_acceptance_override"] == ["pnpm -C apps/desktop test"]
        assert task["assignment_priority_override"] == 60
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_list_tasks_response_exposes_assignment_fields() -> None:
    session = OrchestratorSession(
        session_id="session_tasks_assignment_fields",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
        plan=OrchestratorPlan(
            objective="处理当前项目",
            project_snapshot=ProjectSnapshot(
                project_path="/tmp/demo",
                project_name="demo",
                repository_root="/tmp/demo",
            ),
            tasks=[
                OrchestratorTask(
                    task_id="chat-implement-3",
                    title="聊天指派：补齐会话恢复流程",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    status=OrchestratorTaskStatus.RUNNING,
                    assignment_source="chat_assignment",
                    assignment_directive="任务：补齐会话恢复流程",
                    assignment_requested_objective="补齐会话恢复流程",
                    assignment_scope_override=["services/core/app/api"],
                    assignment_resolved_scope_override=["services/core/app/api"],
                    assignment_acceptance_override=["pytest -q services/core/tests/test_api_orchestrator.py"],
                    assignment_priority_override=40,
                )
            ],
        ),
    )
    service = StubOrchestratorService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.get(f"/orchestrator/sessions/{session.session_id}/tasks")
        assert response.status_code == 200

        tasks = response.json()
        assert isinstance(tasks, list)
        assert len(tasks) == 1
        task = tasks[0]
        assert task["assignment_source"] == "chat_assignment"
        assert task["assignment_directive"] == "任务：补齐会话恢复流程"
        assert task["assignment_requested_objective"] == "补齐会话恢复流程"
        assert task["assignment_scope_override"] == ["services/core/app/api"]
        assert task["assignment_resolved_scope_override"] == ["services/core/app/api"]
        assert task["assignment_acceptance_override"] == ["pytest -q services/core/tests/test_api_orchestrator.py"]
        assert task["assignment_priority_override"] == 40
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_delete_session_endpoint_returns_delete_receipt() -> None:
    session = OrchestratorSession(
        session_id="session-delete-1",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )

    class StubDeleteSessionService(StubOrchestratorService):
        def __init__(self, base_session: OrchestratorSession) -> None:
            super().__init__(base_session)
            self.deleted_session_id: str | None = None

        def delete_session(self, session_id: str, *, hub=None) -> int:
            _ = hub
            self.deleted_session_id = session_id
            return 4

    service = StubDeleteSessionService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.delete(f"/orchestrator/sessions/{session.session_id}")
        assert response.status_code == 200
        assert response.json() == {
            "session_id": session.session_id,
            "deleted": True,
            "cleared_messages": 4,
        }
        assert service.deleted_session_id == session.session_id
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_stop_delegate_endpoint_returns_updated_session() -> None:
    session = OrchestratorSession(
        session_id="session_stop_delegate",
        project_path="/tmp/demo",
        project_name="demo",
        goal="处理当前项目",
    )

    class StubStopDelegateService(StubOrchestratorService):
        def __init__(self, base_session: OrchestratorSession) -> None:
            super().__init__(base_session)
            self.stop_payload: dict[str, object] | None = None

        def stop_delegate(self, payload, *, hub=None):
            _ = hub
            self.stop_payload = payload.model_dump(mode="json")
            self.session = self.session.model_copy(
                update={
                    "status": OrchestratorSessionStatus.FAILED,
                    "summary": "主控已停止任务：示例任务",
                    "coordination": OrchestratorSessionCoordination(
                        mode=OrchestratorCoordinationMode.FAILED,
                        priority_score=1,
                        waiting_reason="主控已停止任务：示例任务",
                        failure_category="delegate_failure",
                    ),
                }
            )
            return self.session

    service = StubStopDelegateService(session)
    conversation_service = StubOrchestratorConversationService()

    app.dependency_overrides[get_orchestrator_service] = lambda: service
    app.dependency_overrides[get_orchestrator_conversation_service] = lambda: conversation_service

    try:
        client = TestClient(app)
        response = client.post(
            "/orchestrator/delegates/stop",
            json={
                "session_id": session.session_id,
                "task_id": "task-1",
                "delegate_run_id": "run-1",
                "reason": "手动停止",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert service.stop_payload is not None
        assert service.stop_payload["task_id"] == "task-1"
        assert service.stop_payload["delegate_run_id"] == "run-1"
    finally:
        app.dependency_overrides.clear()
