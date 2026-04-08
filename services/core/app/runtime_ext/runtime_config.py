from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any
from typing import ClassVar, Literal

from app.config import get_chat_context_limit, get_chat_model, get_chat_provider, get_chat_read_timeout_seconds

FolderAccessLevel = Literal["read_only", "full_access"]
GOAL_ADMISSION_HISTORY_MAX_ENTRIES = 50


class RuntimeConfig:
    """Runtime-tunable config values."""

    _instance: ClassVar["RuntimeConfig"] | None = None
    _instance_lock: ClassVar[Lock] = Lock()

    @classmethod
    def _initialize_instance(cls) -> "RuntimeConfig":
        instance = super().__new__(cls)
        instance._lock = Lock()
        instance._chat_context_limit = get_chat_context_limit()
        instance._chat_provider = get_chat_provider()
        instance._chat_model = get_chat_model()
        instance._chat_read_timeout_seconds = get_chat_read_timeout_seconds()
        instance._self_programming_hard_failure_cooldown_minutes = 60
        instance._self_programming_proactive_cooldown_minutes = 720
        instance._goal_admission_stability_warning_rate = 0.6
        instance._goal_admission_stability_danger_rate = 0.35
        instance._goal_admission_config_revision = 0
        instance._goal_admission_config_history = []
        instance._append_goal_admission_history_locked(source="bootstrap")
        instance._folder_permissions = {}
        return instance

    @classmethod
    def _ensure_instance_fields(cls, instance: "RuntimeConfig") -> None:
        if not hasattr(instance, "_lock"):
            instance._lock = Lock()
        with instance._lock:
            if not hasattr(instance, "_chat_context_limit"):
                instance._chat_context_limit = get_chat_context_limit()
            if not hasattr(instance, "_chat_provider"):
                instance._chat_provider = get_chat_provider()
            if not hasattr(instance, "_chat_model"):
                instance._chat_model = get_chat_model()
            if not hasattr(instance, "_chat_read_timeout_seconds"):
                instance._chat_read_timeout_seconds = get_chat_read_timeout_seconds()
            if not hasattr(instance, "_self_programming_hard_failure_cooldown_minutes"):
                instance._self_programming_hard_failure_cooldown_minutes = 60
            if not hasattr(instance, "_self_programming_proactive_cooldown_minutes"):
                instance._self_programming_proactive_cooldown_minutes = 720
            if not hasattr(instance, "_goal_admission_stability_warning_rate"):
                instance._goal_admission_stability_warning_rate = 0.6
            if not hasattr(instance, "_goal_admission_stability_danger_rate"):
                instance._goal_admission_stability_danger_rate = 0.35
            if not hasattr(instance, "_goal_admission_config_revision"):
                instance._goal_admission_config_revision = 0
            if not hasattr(instance, "_goal_admission_config_history") or not isinstance(
                instance._goal_admission_config_history,
                list,
            ):
                instance._goal_admission_config_history = []
            if not instance._goal_admission_config_history:
                instance._append_goal_admission_history_locked(source="bootstrap")
            if not hasattr(instance, "_folder_permissions") or not isinstance(instance._folder_permissions, dict):
                instance._folder_permissions = {}

    def __new__(cls) -> "RuntimeConfig":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls._initialize_instance()
            else:
                cls._ensure_instance_fields(cls._instance)
            return cls._instance

    @property
    def chat_context_limit(self) -> int:
        with self._lock:
            return self._chat_context_limit

    @chat_context_limit.setter
    def chat_context_limit(self, value: int) -> None:
        with self._lock:
            self._chat_context_limit = max(1, min(20, value))

    @property
    def chat_provider(self) -> str:
        with self._lock:
            return self._chat_provider

    @chat_provider.setter
    def chat_provider(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        with self._lock:
            self._chat_provider = normalized

    @property
    def chat_model(self) -> str:
        with self._lock:
            return self._chat_model

    @chat_model.setter
    def chat_model(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        with self._lock:
            self._chat_model = normalized

    @property
    def chat_read_timeout_seconds(self) -> int:
        with self._lock:
            return self._chat_read_timeout_seconds

    @chat_read_timeout_seconds.setter
    def chat_read_timeout_seconds(self, value: int) -> None:
        with self._lock:
            self._chat_read_timeout_seconds = max(10, min(600, int(value)))

    @property
    def self_programming_hard_failure_cooldown_minutes(self) -> int:
        with self._lock:
            return self._self_programming_hard_failure_cooldown_minutes

    @self_programming_hard_failure_cooldown_minutes.setter
    def self_programming_hard_failure_cooldown_minutes(self, value: int) -> None:
        with self._lock:
            self._self_programming_hard_failure_cooldown_minutes = max(1, min(7 * 24 * 60, int(value)))

    @property
    def self_programming_proactive_cooldown_minutes(self) -> int:
        with self._lock:
            return self._self_programming_proactive_cooldown_minutes

    @self_programming_proactive_cooldown_minutes.setter
    def self_programming_proactive_cooldown_minutes(self, value: int) -> None:
        with self._lock:
            self._self_programming_proactive_cooldown_minutes = max(1, min(7 * 24 * 60, int(value)))

    @property
    def goal_admission_stability_warning_rate(self) -> float:
        with self._lock:
            return self._goal_admission_stability_warning_rate

    @goal_admission_stability_warning_rate.setter
    def goal_admission_stability_warning_rate(self, value: float) -> None:
        with self._lock:
            self._goal_admission_stability_warning_rate = max(0.0, min(1.0, float(value)))

    @property
    def goal_admission_stability_danger_rate(self) -> float:
        with self._lock:
            return self._goal_admission_stability_danger_rate

    @goal_admission_stability_danger_rate.setter
    def goal_admission_stability_danger_rate(self, value: float) -> None:
        with self._lock:
            self._goal_admission_stability_danger_rate = max(0.0, min(1.0, float(value)))

    def _append_goal_admission_history_locked(
        self,
        *,
        source: str,
        rolled_back_from_revision: int | None = None,
    ) -> dict[str, Any]:
        self._goal_admission_config_revision += 1
        entry: dict[str, Any] = {
            "revision": self._goal_admission_config_revision,
            "source": source,
            "stability_warning_rate": self._goal_admission_stability_warning_rate,
            "stability_danger_rate": self._goal_admission_stability_danger_rate,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rolled_back_from_revision": rolled_back_from_revision,
        }
        self._goal_admission_config_history.append(entry)
        if len(self._goal_admission_config_history) > GOAL_ADMISSION_HISTORY_MAX_ENTRIES:
            self._goal_admission_config_history = self._goal_admission_config_history[-GOAL_ADMISSION_HISTORY_MAX_ENTRIES:]
        return dict(entry)

    def list_goal_admission_config_history(self, limit: int = 10) -> list[dict[str, Any]]:
        requested = max(1, min(GOAL_ADMISSION_HISTORY_MAX_ENTRIES, int(limit)))
        with self._lock:
            snapshot = [dict(item) for item in self._goal_admission_config_history[-requested:]]
        return list(reversed(snapshot))

    def update_goal_admission_thresholds(
        self,
        *,
        stability_warning_rate: float | None = None,
        stability_danger_rate: float | None = None,
        source: str = "manual_update",
    ) -> dict[str, float | int]:
        with self._lock:
            next_warning = (
                self._goal_admission_stability_warning_rate
                if stability_warning_rate is None
                else max(0.0, min(1.0, float(stability_warning_rate)))
            )
            next_danger = (
                self._goal_admission_stability_danger_rate
                if stability_danger_rate is None
                else max(0.0, min(1.0, float(stability_danger_rate)))
            )
            if next_danger > next_warning:
                raise ValueError("stability_danger_rate must be <= stability_warning_rate")
            changed = (
                next_warning != self._goal_admission_stability_warning_rate
                or next_danger != self._goal_admission_stability_danger_rate
            )
            self._goal_admission_stability_warning_rate = next_warning
            self._goal_admission_stability_danger_rate = next_danger
            if changed:
                revision = int(self._append_goal_admission_history_locked(source=source)["revision"])
            else:
                revision = int(self._goal_admission_config_revision)
            return {
                "stability_warning_rate": self._goal_admission_stability_warning_rate,
                "stability_danger_rate": self._goal_admission_stability_danger_rate,
                "revision": revision,
            }

    def rollback_goal_admission_thresholds(self) -> dict[str, float | int]:
        with self._lock:
            if len(self._goal_admission_config_history) < 2:
                raise ValueError("no previous goal-admission config revision to rollback")
            previous_entry = self._goal_admission_config_history[-2]
            rolled_back_from_revision = int(self._goal_admission_config_history[-1]["revision"])
            self._goal_admission_stability_warning_rate = float(previous_entry["stability_warning_rate"])
            self._goal_admission_stability_danger_rate = float(previous_entry["stability_danger_rate"])
            history_entry = self._append_goal_admission_history_locked(
                source="rollback",
                rolled_back_from_revision=rolled_back_from_revision,
            )
            return {
                "stability_warning_rate": self._goal_admission_stability_warning_rate,
                "stability_danger_rate": self._goal_admission_stability_danger_rate,
                "rolled_back_from_revision": rolled_back_from_revision,
                "revision": int(history_entry["revision"]),
            }

    def list_folder_permissions(self) -> list[tuple[str, FolderAccessLevel]]:
        with self._lock:
            entries = list(self._folder_permissions.items())
        return sorted(entries, key=lambda item: item[0])

    def set_folder_permission(self, folder_path: str, access_level: FolderAccessLevel) -> None:
        with self._lock:
            self._folder_permissions[folder_path] = access_level

    def remove_folder_permission(self, folder_path: str) -> bool:
        with self._lock:
            return self._folder_permissions.pop(folder_path, None) is not None

    def clear_folder_permissions(self) -> None:
        with self._lock:
            self._folder_permissions.clear()


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig()
