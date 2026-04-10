from fastapi.testclient import TestClient

from app.main import (
    app,
    get_chat_gateway,
    get_orchestrator_conversation_service,
    get_orchestrator_service,
)
from app.domain.models import OrchestratorSession, OrchestratorSessionStatus
from app.orchestrator.conversation_models import OrchestratorChatSubmissionResult


class StubOrchestratorService:
    def __init__(self, session: OrchestratorSession) -> None:
        self.session = session
        self.apply_directive_calls = 0
        self.resume_calls = 0
        self.approve_calls = 0
        self.reject_calls = 0

    def get_session(self, session_id: str) -> OrchestratorSession:
        assert session_id == self.session.session_id
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


class StubOrchestratorConversationService:
    def __init__(self) -> None:
        self.user_messages: list[str] = []
        self.stream_calls = 0
        self.cleared_session_ids: list[str] = []

    def append_user_message(self, session_id: str, message: str, *, hub=None):
        _ = (session_id, hub)
        self.user_messages.append(message)

    def stream_assistant_reply(self, session: OrchestratorSession, user_message: str, *, gateway, hub=None):
        _ = (gateway, hub, user_message)
        self.stream_calls += 1
        return OrchestratorChatSubmissionResult(
            session_id=session.session_id,
            assistant_message_id="assistant_test_1",
        )

    def append_assistant_message(self, session: OrchestratorSession, reply: str, *, hub=None):
        _ = (session, reply, hub)
        raise AssertionError("append_assistant_message should not be called in fallback path")

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
        def append_assistant_message(self, session: OrchestratorSession, reply: str, *, hub=None):
            _ = (session, hub)
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
