from logging import getLogger

from app.api.chat_postprocess import finalize_chat_submission
from app.api.chat_reasoning import ChatReasoningController
from app.domain.models import BeingState, WakeMode
from app.llm.schemas import ChatSubmissionResult
from app.memory.repository import InMemoryMemoryRepository
from app.persona.service import InMemoryPersonaRepository, PersonaService
from app.runtime import StateStore


class _StubChatMemoryRuntime:
    def record_exchange(self, *args, **kwargs) -> bool:
        return True


def _build_submission() -> ChatSubmissionResult:
    return ChatSubmissionResult(
        response_id="resp_1",
        assistant_message_id="assistant_1",
    )


def _build_reasoning() -> ChatReasoningController:
    return ChatReasoningController(logger=getLogger(__name__))


def test_finalize_chat_submission_uses_focus_subject_for_focus_effort():
    memory_repository = InMemoryMemoryRepository()
    personality = PersonaService(repository=InMemoryPersonaRepository()).profile.personality
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "goal_backed_attention",
                "title": "你刚才提到最近提不起劲",
                "why_now": "这句话我还挂着。",
                "goal_id": "goal-focus",
            },
        ),
        memory_repository=memory_repository,
    )

    finalize_chat_submission(
        assistant_message_id="assistant_1",
        chat_memory_runtime=_StubChatMemoryRuntime(),
        knowledge_extraction_enabled=False,
        logger=getLogger(__name__),
        memory_repository=memory_repository,
        personality=personality,
        reasoning=_build_reasoning(),
        reasoning_state=None,
        state_store=state_store,
        submission=_build_submission(),
        tracker=None,
        user_message="我最近挺累的，感觉做什么都提不起劲",
        output_text="我们先别急着定目标，先把这股提不起劲的感觉理一理。",
        request_key="request_1",
    )

    latest_state = state_store.get()
    assert latest_state.focus_effort is not None
    assert latest_state.focus_effort.goal_id == "goal-focus"
    assert latest_state.focus_effort.goal_title == "你刚才提到最近提不起劲"


def test_finalize_chat_submission_does_not_fallback_without_focus_subject():
    memory_repository = InMemoryMemoryRepository()
    personality = PersonaService(repository=InMemoryPersonaRepository()).profile.personality
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE), memory_repository=memory_repository)

    finalize_chat_submission(
        assistant_message_id="assistant_1",
        chat_memory_runtime=_StubChatMemoryRuntime(),
        knowledge_extraction_enabled=False,
        logger=getLogger(__name__),
        memory_repository=memory_repository,
        personality=personality,
        reasoning=_build_reasoning(),
        reasoning_state=None,
        state_store=state_store,
        submission=_build_submission(),
        tracker=None,
        user_message="我最近挺累的，感觉做什么都提不起劲",
        output_text="我们先别急着定目标，先把这股提不起劲的感觉理一理。",
        request_key="request_1",
    )

    latest_state = state_store.get()
    assert latest_state.focus_effort is None
