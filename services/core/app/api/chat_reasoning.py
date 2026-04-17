from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from logging import Logger
from threading import Lock
from uuid import uuid4

from app.llm.schemas import ChatReasoningState, ChatResumeRequest
from app.memory.repository import MemoryRepository


class ChatReasoningController:
    """Tracks chat-side reasoning sessions for status continuity and resume flow."""

    def __init__(self, *, logger: Logger, recovery_scan_limit: int = 800) -> None:
        self._logger = logger
        self._recovery_scan_limit = recovery_scan_limit
        self._sessions: dict[str, dict[str, object]] = {}
        self._assistant_map: dict[str, str] = {}
        self._lock = Lock()

    def resolve_resume_reasoning_session_id(
        self,
        request_body: ChatResumeRequest,
        *,
        memory_repository: MemoryRepository,
    ) -> str | None:
        explicit = self.normalize_reasoning_session_id(request_body.reasoning_session_id)
        if explicit:
            return explicit

        normalized_assistant_message_id = (request_body.assistant_message_id or "").strip()
        if not normalized_assistant_message_id:
            return None

        with self._lock:
            remembered = self._assistant_map.get(normalized_assistant_message_id)
        if remembered:
            return remembered

        try:
          recent_chat_events = memory_repository.list_recent_chat(limit=self._recovery_scan_limit)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("resume reasoning recovery scan failed: %s", exc)
            return None

        for event in recent_chat_events:
            if event.role != "assistant":
                continue
            if self.normalize_reasoning_session_id(event.session_id) != normalized_assistant_message_id:
                continue
            recovered_reasoning_state = self.coerce_reasoning_state(event.reasoning_state)
            recovered_reasoning_session_id = self.normalize_reasoning_session_id(event.reasoning_session_id)
            if recovered_reasoning_session_id is None and recovered_reasoning_state is not None:
                recovered_reasoning_session_id = self.normalize_reasoning_session_id(recovered_reasoning_state.session_id)
            if recovered_reasoning_session_id is None:
                continue
            if recovered_reasoning_state is not None:
                self.hydrate_reasoning_session_state(recovered_reasoning_state)
            self.remember_reasoning_session_for_assistant(
                normalized_assistant_message_id,
                recovered_reasoning_session_id,
            )
            return recovered_reasoning_session_id
        return None

    def start_reasoning_session(self, *, user_message: str, session_id: str | None) -> ChatReasoningState:
        normalized_session_id = self.normalize_reasoning_session_id(session_id) or f"reasoning_{uuid4().hex}"
        with self._lock:
            previous = self._sessions.get(normalized_session_id)
            previous_step = int(previous.get("step_index", 0)) if isinstance(previous, dict) else 0
            step_index = max(1, previous_step + 1)
            state = ChatReasoningState(
                session_id=normalized_session_id,
                phase="exploring",
                step_index=step_index,
                summary=(user_message or "").strip()[:72] or "继续推理中",
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._sessions[normalized_session_id] = state.model_dump(mode="json")
            return state

    def update_reasoning_session_after_completion(
        self,
        *,
        reasoning_state: ChatReasoningState | None,
        user_message: str,
        output_text: str,
        compact_text: Callable[..., str],
    ) -> ChatReasoningState | None:
        if reasoning_state is None:
            return None

        completion_markers = ("结论", "总结", "已完成", "final", "done")
        is_completed = any(marker in (output_text or "").lower() for marker in completion_markers)
        summarized = compact_text(output_text or user_message, limit=120) or "继续推理中"
        updated = reasoning_state.model_copy(
            update={
                "phase": "completed" if is_completed else "exploring",
                "summary": summarized,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        with self._lock:
            self._sessions[updated.session_id] = updated.model_dump(mode="json")
        return updated

    def remember_reasoning_session_for_assistant(self, assistant_message_id: str, reasoning_session_id: str) -> None:
        with self._lock:
            self._assistant_map[assistant_message_id] = reasoning_session_id

    def hydrate_reasoning_session_state(self, reasoning_state: ChatReasoningState) -> None:
        with self._lock:
            self._sessions[reasoning_state.session_id] = reasoning_state.model_dump(mode="json")

    @staticmethod
    def append_reasoning_instruction(
        instructions: str,
        *,
        reasoning_state: ChatReasoningState | None,
    ) -> str:
        if reasoning_state is None:
            return instructions
        return (
            f"{instructions}\n\n"
            "[Continuous Reasoning]\n"
            f"你正在同一个持续推理会话中（session={reasoning_state.session_id}, step={reasoning_state.step_index}, phase={reasoning_state.phase}）。\n"
            "请延续已有推理，不要重置上下文；输出时先给结论，再给一段简短“阶段摘要”，但不要泄露完整思维链。"
        )

    @staticmethod
    def normalize_reasoning_session_id(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def coerce_reasoning_state(value: object) -> ChatReasoningState | None:
        if not isinstance(value, dict):
            return None
        try:
            return ChatReasoningState.model_validate(value)
        except Exception:  # noqa: BLE001
            return None
