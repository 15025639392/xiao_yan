from __future__ import annotations

from pathlib import Path
from threading import Lock

from app.domain.models import OrchestratorSession
from app.utils.file_utils import read_json_file, write_json_file


class OrchestratorSessionRepository:
    def __init__(self, storage_path: Path | None = None, *, in_memory: bool = False) -> None:
        self._lock = Lock()
        self._storage_path = None if in_memory else storage_path
        self._sessions: dict[str, OrchestratorSession] = self._load_sessions()

    def get(self, session_id: str) -> OrchestratorSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            return None if session is None else session.model_copy(deep=True)

    def save(self, session: OrchestratorSession) -> OrchestratorSession:
        with self._lock:
            self._sessions[session.session_id] = session.model_copy(deep=True)
            self._persist_locked()
            return self._sessions[session.session_id].model_copy(deep=True)

    def list_sessions(self) -> list[OrchestratorSession]:
        with self._lock:
            sessions = [session.model_copy(deep=True) for session in self._sessions.values()]
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def _load_sessions(self) -> dict[str, OrchestratorSession]:
        if self._storage_path is None or not self._storage_path.exists():
            return {}

        payload = read_json_file(self._storage_path)
        raw_sessions = payload.get("sessions", []) if isinstance(payload, dict) else []
        sessions: dict[str, OrchestratorSession] = {}
        for raw in raw_sessions:
            session = OrchestratorSession.model_validate(raw)
            sessions[session.session_id] = session
        return sessions

    def _persist_locked(self) -> None:
        if self._storage_path is None:
            return

        write_json_file(
            self._storage_path,
            {
                "sessions": [
                    session.model_dump(mode="json")
                    for session in sorted(self._sessions.values(), key=lambda item: item.updated_at)
                ]
            },
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
