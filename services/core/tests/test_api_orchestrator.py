from fastapi.testclient import TestClient

from app.main import (
    app,
    get_chat_gateway,
    get_orchestrator_conversation_service,
    get_orchestrator_service,
)
from app.domain.models import OrchestratorSession
from app.orchestrator.conversation_models import OrchestratorChatSubmissionResult


class StubOrchestratorService:
    def __init__(self, session: OrchestratorSession) -> None:
        self.session = session
        self.apply_directive_calls = 0

    def get_session(self, session_id: str) -> OrchestratorSession:
        assert session_id == self.session.session_id
        return self.session

    def apply_directive(self, session_id: str, message: str, *, hub=None) -> OrchestratorSession:
        _ = (session_id, message, hub)
        self.apply_directive_calls += 1
        raise ValueError("unsupported orchestrator directive")


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
