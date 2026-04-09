from __future__ import annotations

from pathlib import Path
from threading import Lock

from app.orchestrator.conversation_models import OrchestratorMessage
from app.utils.file_utils import read_json_file, write_json_file


class OrchestratorConversationRepository:
    def __init__(self, storage_path: Path | None = None, *, in_memory: bool = False) -> None:
        self._lock = Lock()
        self._storage_path = None if in_memory else storage_path
        self._messages_by_session = self._load_messages()

    def list_messages(self, session_id: str) -> list[OrchestratorMessage]:
        with self._lock:
            messages = self._messages_by_session.get(session_id, [])
            return [message.model_copy(deep=True) for message in messages]

    def get(self, session_id: str, message_id: str) -> OrchestratorMessage | None:
        with self._lock:
            for message in self._messages_by_session.get(session_id, []):
                if message.message_id == message_id:
                    return message.model_copy(deep=True)
        return None

    def append(self, message: OrchestratorMessage) -> OrchestratorMessage:
        with self._lock:
            self._messages_by_session.setdefault(message.session_id, []).append(message.model_copy(deep=True))
            self._persist_locked()
            return self._messages_by_session[message.session_id][-1].model_copy(deep=True)

    def clear_session(self, session_id: str) -> int:
        with self._lock:
            bucket = self._messages_by_session.pop(session_id, None)
            removed = 0 if bucket is None else len(bucket)
            self._persist_locked()
            return removed

    def save(self, message: OrchestratorMessage) -> OrchestratorMessage:
        with self._lock:
            bucket = self._messages_by_session.setdefault(message.session_id, [])
            for index, current in enumerate(bucket):
                if current.message_id == message.message_id:
                    bucket[index] = message.model_copy(deep=True)
                    self._persist_locked()
                    return bucket[index].model_copy(deep=True)
            bucket.append(message.model_copy(deep=True))
            self._persist_locked()
            return bucket[-1].model_copy(deep=True)

    def _load_messages(self) -> dict[str, list[OrchestratorMessage]]:
        if self._storage_path is None or not self._storage_path.exists():
            return {}

        payload = read_json_file(self._storage_path)
        raw_messages = payload.get("messages", []) if isinstance(payload, dict) else []
        messages_by_session: dict[str, list[OrchestratorMessage]] = {}
        for raw in raw_messages:
            message = OrchestratorMessage.model_validate(raw)
            messages_by_session.setdefault(message.session_id, []).append(message)
        for bucket in messages_by_session.values():
            bucket.sort(key=lambda item: item.created_at)
        return messages_by_session

    def _persist_locked(self) -> None:
        if self._storage_path is None:
            return

        flattened: list[OrchestratorMessage] = []
        for session_id in sorted(self._messages_by_session):
            flattened.extend(sorted(self._messages_by_session[session_id], key=lambda item: item.created_at))

        write_json_file(
            self._storage_path,
            {
                "messages": [
                    message.model_dump(mode="json")
                    for message in flattened
                ]
            },
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
