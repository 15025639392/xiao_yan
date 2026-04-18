from __future__ import annotations

from logging import Logger
from typing import Any

from app.api.chat_reasoning import ChatReasoningController
from app.focus.effort import chat_reply_effort
from app.llm.schemas import ChatMessage, ChatReasoningState, ChatSubmissionResult
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.extractor import MemoryExtractor
from app.memory.models import MemoryEvent
from app.memory.observability import KnowledgeObservabilityTracker
from app.memory.repository import MemoryRepository
from app.runtime import StateStore


def compact_text(text: str | None, *, limit: int) -> str:
    if not text:
        return ""
    compacted = " ".join(text.strip().split())
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[: limit - 1].rstrip()}…"


def build_post_chat_thought(user_message: str, assistant_response: str) -> str:
    topic = compact_text(user_message, limit=28) or "刚才这段对话"
    first_line = next((line for line in assistant_response.splitlines() if line.strip()), assistant_response)
    assistant_snippet = compact_text(first_line, limit=42)
    if assistant_snippet:
        return f"我刚顺着“{topic}”回应了你，脑子里还停着这句：{assistant_snippet}"
    return f"我刚顺着“{topic}”回应了你，接下来想把它再往前推一小步。"


def mirror_exchange_to_memory_repository(
    *,
    memory_repository: MemoryRepository,
    user_message: str,
    assistant_response: str,
    assistant_session_id: str,
    request_key: str | None = None,
    reasoning_session_id: str | None = None,
    reasoning_state: ChatReasoningState | None = None,
) -> None:
    user_text = (user_message or "").strip()
    assistant_text = (assistant_response or "").strip()
    if not user_text or not assistant_text:
        return

    reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None
    memory_repository.save_event(MemoryEvent(kind="chat", content=user_text, role="user", request_key=request_key))
    memory_repository.save_event(
        MemoryEvent(
            kind="chat",
            content=assistant_text,
            role="assistant",
            session_id=assistant_session_id,
            request_key=request_key,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_payload,
        )
    )


def extract_structured_knowledge_events(
    *,
    memory_repository: MemoryRepository,
    user_message: str,
    assistant_response: str,
    assistant_session_id: str,
    personality: Any,
) -> int:
    user_text = (user_message or "").strip()
    assistant_text = (assistant_response or "").strip()
    if not user_text or not assistant_text:
        return 0

    extractor = MemoryExtractor(personality=personality)
    events = extractor.extract_from_dialogue(
        [
            ChatMessage(role="user", content=user_text),
            ChatMessage(role="assistant", content=assistant_text),
        ],
        {
            "source_ref": f"chat://{assistant_session_id}",
            "version_tag": "v1",
            "topic": compact_text(user_text, limit=40),
        },
    )
    for event in events:
        memory_repository.save_event(event)
    return len(events)


def finalize_chat_submission(
    *,
    assistant_message_id: str,
    chat_memory_runtime: ChatMemoryRuntime,
    knowledge_extraction_enabled: bool,
    logger: Logger,
    memory_repository: MemoryRepository,
    personality: Any,
    reasoning: ChatReasoningController,
    reasoning_state: ChatReasoningState | None,
    state_store: StateStore,
    submission: ChatSubmissionResult,
    tracker: KnowledgeObservabilityTracker | None,
    user_message: str,
    output_text: str,
    request_key: str | None = None,
) -> ChatSubmissionResult:
    finalized_reasoning_state = reasoning.update_reasoning_session_after_completion(
        reasoning_state=reasoning_state,
        user_message=user_message,
        output_text=output_text,
        compact_text=compact_text,
    )
    finalized_reasoning_session_id = (
        finalized_reasoning_state.session_id if finalized_reasoning_state is not None else None
    )

    write_success = False
    try:
        write_success = bool(
            chat_memory_runtime.record_exchange(
                user_message,
                output_text,
                assistant_message_id,
                request_key=request_key,
                reasoning_session_id=finalized_reasoning_session_id,
                reasoning_state=(
                    finalized_reasoning_state.model_dump(mode="json")
                    if finalized_reasoning_state is not None
                    else None
                ),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("MemPalace record_exchange raised unexpectedly: %s", exc)
    finally:
        if tracker is not None:
            tracker.record_write(success=write_success)

    try:
        mirror_exchange_to_memory_repository(
            memory_repository=memory_repository,
            user_message=user_message,
            assistant_response=output_text,
            assistant_session_id=assistant_message_id,
            request_key=request_key,
            reasoning_session_id=finalized_reasoning_session_id,
            reasoning_state=finalized_reasoning_state,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("mirror exchange to memory repository failed: %s", exc)

    if knowledge_extraction_enabled:
        try:
            extract_structured_knowledge_events(
                memory_repository=memory_repository,
                user_message=user_message,
                assistant_response=output_text,
                assistant_session_id=assistant_message_id,
                personality=personality,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("structured knowledge extraction failed: %s", exc)

    latest_state = state_store.get()
    next_thought = build_post_chat_thought(user_message, output_text)
    focus_goal_id = (
        latest_state.active_goal_ids[0]
        if latest_state.active_goal_ids
        else latest_state.today_plan.goal_id if latest_state.today_plan is not None else None
    )
    focus_goal_title = (
        latest_state.today_plan.goal_title
        if latest_state.today_plan is not None
        else ("当前焦点" if latest_state.active_goal_ids else None)
    )
    updates: dict[str, object] = {"current_thought": next_thought}
    if focus_goal_title is not None:
        updates["focus_effort"] = chat_reply_effort(
            goal_id=focus_goal_id,
            goal_title=focus_goal_title,
        )
    state_store.set(latest_state.model_copy(update=updates))

    if finalized_reasoning_state is None:
        return submission

    reasoning.remember_reasoning_session_for_assistant(
        assistant_message_id,
        finalized_reasoning_state.session_id,
    )
    return submission.model_copy(
        update={
            "request_key": request_key,
            "reasoning_session_id": finalized_reasoning_state.session_id,
            "reasoning_state": finalized_reasoning_state,
        }
    )
