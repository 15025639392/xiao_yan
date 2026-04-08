from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any
from typing import ClassVar, Literal

from app.capabilities.file_policy import (
    DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS,
    DEFAULT_MAX_LIST_ENTRIES,
    DEFAULT_MAX_READ_BYTES,
    DEFAULT_MAX_SEARCH_RESULTS,
    DEFAULT_MAX_WRITE_BYTES,
    FILE_POLICY_VERSION,
    build_file_policy_payload,
    normalize_file_policy_values,
)
from app.capabilities.shell_policy import (
    DEFAULT_ALLOWED_EXECUTABLES,
    DEFAULT_ALLOWED_GIT_SUBCOMMANDS,
    SHELL_POLICY_VERSION,
    build_shell_policy_payload,
    normalize_shell_policy_values,
)
from app.config import (
    get_chat_context_limit,
    get_chat_model,
    get_chat_provider,
    get_chat_read_timeout_seconds,
    get_goal_admission_chain_defer_score,
    get_goal_admission_chain_min_score,
    get_goal_admission_defer_score,
    get_goal_admission_min_score,
    get_goal_admission_world_defer_score,
    get_goal_admission_world_min_score,
)

FolderAccessLevel = Literal["read_only", "full_access"]
GOAL_ADMISSION_HISTORY_MAX_ENTRIES = 50
CAPABILITY_POLICY_HISTORY_MAX_ENTRIES = 50


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
        instance._goal_admission_user_topic_min_score = get_goal_admission_min_score()
        instance._goal_admission_user_topic_defer_score = get_goal_admission_defer_score()
        instance._goal_admission_world_event_min_score = get_goal_admission_world_min_score()
        instance._goal_admission_world_event_defer_score = get_goal_admission_world_defer_score()
        instance._goal_admission_chain_next_min_score = get_goal_admission_chain_min_score()
        instance._goal_admission_chain_next_defer_score = get_goal_admission_chain_defer_score()
        instance._goal_admission_config_revision = 0
        instance._goal_admission_config_history = []
        instance._append_goal_admission_history_locked(source="bootstrap")
        instance._capability_shell_policy_revision = 0
        instance._capability_shell_policy_allowed_executables = list(DEFAULT_ALLOWED_EXECUTABLES)
        instance._capability_shell_policy_allowed_git_subcommands = list(DEFAULT_ALLOWED_GIT_SUBCOMMANDS)
        instance._capability_shell_policy_history = []
        instance._append_capability_shell_policy_history_locked(source="bootstrap")
        instance._capability_file_policy_revision = 0
        instance._capability_file_policy_max_read_bytes = DEFAULT_MAX_READ_BYTES
        instance._capability_file_policy_max_write_bytes = DEFAULT_MAX_WRITE_BYTES
        instance._capability_file_policy_max_search_results = DEFAULT_MAX_SEARCH_RESULTS
        instance._capability_file_policy_max_list_entries = DEFAULT_MAX_LIST_ENTRIES
        instance._capability_file_policy_allowed_search_file_patterns = list(DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS)
        instance._capability_file_policy_history = []
        instance._append_capability_file_policy_history_locked(source="bootstrap")
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
            if not hasattr(instance, "_goal_admission_user_topic_min_score"):
                instance._goal_admission_user_topic_min_score = get_goal_admission_min_score()
            if not hasattr(instance, "_goal_admission_user_topic_defer_score"):
                instance._goal_admission_user_topic_defer_score = get_goal_admission_defer_score()
            if not hasattr(instance, "_goal_admission_world_event_min_score"):
                instance._goal_admission_world_event_min_score = get_goal_admission_world_min_score()
            if not hasattr(instance, "_goal_admission_world_event_defer_score"):
                instance._goal_admission_world_event_defer_score = get_goal_admission_world_defer_score()
            if not hasattr(instance, "_goal_admission_chain_next_min_score"):
                instance._goal_admission_chain_next_min_score = get_goal_admission_chain_min_score()
            if not hasattr(instance, "_goal_admission_chain_next_defer_score"):
                instance._goal_admission_chain_next_defer_score = get_goal_admission_chain_defer_score()
            if not hasattr(instance, "_goal_admission_config_revision"):
                instance._goal_admission_config_revision = 0
            if not hasattr(instance, "_goal_admission_config_history") or not isinstance(
                instance._goal_admission_config_history,
                list,
            ):
                instance._goal_admission_config_history = []
            if not instance._goal_admission_config_history:
                instance._append_goal_admission_history_locked(source="bootstrap")
            if not hasattr(instance, "_capability_shell_policy_revision"):
                instance._capability_shell_policy_revision = 0
            if not hasattr(instance, "_capability_shell_policy_allowed_executables") or not isinstance(
                instance._capability_shell_policy_allowed_executables,
                list,
            ):
                instance._capability_shell_policy_allowed_executables = list(DEFAULT_ALLOWED_EXECUTABLES)
            if not hasattr(instance, "_capability_shell_policy_allowed_git_subcommands") or not isinstance(
                instance._capability_shell_policy_allowed_git_subcommands,
                list,
            ):
                instance._capability_shell_policy_allowed_git_subcommands = list(DEFAULT_ALLOWED_GIT_SUBCOMMANDS)
            if not hasattr(instance, "_capability_shell_policy_history") or not isinstance(
                instance._capability_shell_policy_history,
                list,
            ):
                instance._capability_shell_policy_history = []
            if not instance._capability_shell_policy_history:
                instance._append_capability_shell_policy_history_locked(source="bootstrap")

            if not hasattr(instance, "_capability_file_policy_revision"):
                instance._capability_file_policy_revision = 0
            if not hasattr(instance, "_capability_file_policy_max_read_bytes"):
                instance._capability_file_policy_max_read_bytes = DEFAULT_MAX_READ_BYTES
            if not hasattr(instance, "_capability_file_policy_max_write_bytes"):
                instance._capability_file_policy_max_write_bytes = DEFAULT_MAX_WRITE_BYTES
            if not hasattr(instance, "_capability_file_policy_max_search_results"):
                instance._capability_file_policy_max_search_results = DEFAULT_MAX_SEARCH_RESULTS
            if not hasattr(instance, "_capability_file_policy_max_list_entries"):
                instance._capability_file_policy_max_list_entries = DEFAULT_MAX_LIST_ENTRIES
            if not hasattr(instance, "_capability_file_policy_allowed_search_file_patterns") or not isinstance(
                instance._capability_file_policy_allowed_search_file_patterns,
                list,
            ):
                instance._capability_file_policy_allowed_search_file_patterns = list(DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS)
            if not hasattr(instance, "_capability_file_policy_history") or not isinstance(
                instance._capability_file_policy_history,
                list,
            ):
                instance._capability_file_policy_history = []
            if not instance._capability_file_policy_history:
                instance._append_capability_file_policy_history_locked(source="bootstrap")
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

    @property
    def goal_admission_user_topic_min_score(self) -> float:
        with self._lock:
            return self._goal_admission_user_topic_min_score

    @goal_admission_user_topic_min_score.setter
    def goal_admission_user_topic_min_score(self, value: float) -> None:
        with self._lock:
            self._goal_admission_user_topic_min_score = max(0.0, min(1.0, float(value)))

    @property
    def goal_admission_user_topic_defer_score(self) -> float:
        with self._lock:
            return self._goal_admission_user_topic_defer_score

    @goal_admission_user_topic_defer_score.setter
    def goal_admission_user_topic_defer_score(self, value: float) -> None:
        with self._lock:
            self._goal_admission_user_topic_defer_score = max(0.0, min(1.0, float(value)))

    @property
    def goal_admission_world_event_min_score(self) -> float:
        with self._lock:
            return self._goal_admission_world_event_min_score

    @goal_admission_world_event_min_score.setter
    def goal_admission_world_event_min_score(self, value: float) -> None:
        with self._lock:
            self._goal_admission_world_event_min_score = max(0.0, min(1.0, float(value)))

    @property
    def goal_admission_world_event_defer_score(self) -> float:
        with self._lock:
            return self._goal_admission_world_event_defer_score

    @goal_admission_world_event_defer_score.setter
    def goal_admission_world_event_defer_score(self, value: float) -> None:
        with self._lock:
            self._goal_admission_world_event_defer_score = max(0.0, min(1.0, float(value)))

    @property
    def goal_admission_chain_next_min_score(self) -> float:
        with self._lock:
            return self._goal_admission_chain_next_min_score

    @goal_admission_chain_next_min_score.setter
    def goal_admission_chain_next_min_score(self, value: float) -> None:
        with self._lock:
            self._goal_admission_chain_next_min_score = max(0.0, min(1.0, float(value)))

    @property
    def goal_admission_chain_next_defer_score(self) -> float:
        with self._lock:
            return self._goal_admission_chain_next_defer_score

    @goal_admission_chain_next_defer_score.setter
    def goal_admission_chain_next_defer_score(self, value: float) -> None:
        with self._lock:
            self._goal_admission_chain_next_defer_score = max(0.0, min(1.0, float(value)))

    @property
    def capability_shell_policy_revision(self) -> int:
        with self._lock:
            return int(self._capability_shell_policy_revision)

    @property
    def capability_file_policy_revision(self) -> int:
        with self._lock:
            return int(self._capability_file_policy_revision)

    def _append_capability_shell_policy_history_locked(self, *, source: str) -> dict[str, Any]:
        self._capability_shell_policy_revision += 1
        entry: dict[str, Any] = {
            "revision": self._capability_shell_policy_revision,
            "source": source,
            "version": SHELL_POLICY_VERSION,
            "allowed_executables": list(self._capability_shell_policy_allowed_executables),
            "allowed_git_subcommands": list(self._capability_shell_policy_allowed_git_subcommands),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._capability_shell_policy_history.append(entry)
        if len(self._capability_shell_policy_history) > CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            self._capability_shell_policy_history = self._capability_shell_policy_history[
                -CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            ]
        return dict(entry)

    def list_capability_shell_policy_history(self, limit: int = 10) -> list[dict[str, Any]]:
        requested = max(1, min(CAPABILITY_POLICY_HISTORY_MAX_ENTRIES, int(limit)))
        with self._lock:
            snapshot = [dict(item) for item in self._capability_shell_policy_history[-requested:]]
        return list(reversed(snapshot))

    def get_capability_shell_policy(self) -> dict[str, Any]:
        with self._lock:
            return build_shell_policy_payload(
                allowed_executables=list(self._capability_shell_policy_allowed_executables),
                allowed_git_subcommands=list(self._capability_shell_policy_allowed_git_subcommands),
                revision=int(self._capability_shell_policy_revision),
            )

    def update_capability_shell_policy(
        self,
        *,
        allowed_executables: list[str] | None = None,
        allowed_git_subcommands: list[str] | None = None,
        source: str = "manual_update",
    ) -> dict[str, Any]:
        with self._lock:
            next_executables, next_git_subcommands = normalize_shell_policy_values(
                allowed_executables=(
                    list(self._capability_shell_policy_allowed_executables)
                    if allowed_executables is None
                    else allowed_executables
                ),
                allowed_git_subcommands=(
                    list(self._capability_shell_policy_allowed_git_subcommands)
                    if allowed_git_subcommands is None
                    else allowed_git_subcommands
                ),
            )
            changed = (
                next_executables != self._capability_shell_policy_allowed_executables
                or next_git_subcommands != self._capability_shell_policy_allowed_git_subcommands
            )
            self._capability_shell_policy_allowed_executables = next_executables
            self._capability_shell_policy_allowed_git_subcommands = next_git_subcommands
            revision = (
                int(self._append_capability_shell_policy_history_locked(source=source)["revision"])
                if changed
                else int(self._capability_shell_policy_revision)
            )
            return build_shell_policy_payload(
                allowed_executables=list(self._capability_shell_policy_allowed_executables),
                allowed_git_subcommands=list(self._capability_shell_policy_allowed_git_subcommands),
                revision=revision,
            )

    def _append_capability_file_policy_history_locked(self, *, source: str) -> dict[str, Any]:
        self._capability_file_policy_revision += 1
        entry: dict[str, Any] = {
            "revision": self._capability_file_policy_revision,
            "source": source,
            "version": FILE_POLICY_VERSION,
            "max_read_bytes": self._capability_file_policy_max_read_bytes,
            "max_write_bytes": self._capability_file_policy_max_write_bytes,
            "max_search_results": self._capability_file_policy_max_search_results,
            "max_list_entries": self._capability_file_policy_max_list_entries,
            "allowed_search_file_patterns": list(self._capability_file_policy_allowed_search_file_patterns),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._capability_file_policy_history.append(entry)
        if len(self._capability_file_policy_history) > CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            self._capability_file_policy_history = self._capability_file_policy_history[-CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:]
        return dict(entry)

    def list_capability_file_policy_history(self, limit: int = 10) -> list[dict[str, Any]]:
        requested = max(1, min(CAPABILITY_POLICY_HISTORY_MAX_ENTRIES, int(limit)))
        with self._lock:
            snapshot = [dict(item) for item in self._capability_file_policy_history[-requested:]]
        return list(reversed(snapshot))

    def get_capability_file_policy(self) -> dict[str, Any]:
        with self._lock:
            return build_file_policy_payload(
                max_read_bytes=int(self._capability_file_policy_max_read_bytes),
                max_write_bytes=int(self._capability_file_policy_max_write_bytes),
                max_search_results=int(self._capability_file_policy_max_search_results),
                max_list_entries=int(self._capability_file_policy_max_list_entries),
                allowed_search_file_patterns=list(self._capability_file_policy_allowed_search_file_patterns),
                revision=int(self._capability_file_policy_revision),
            )

    def update_capability_file_policy(
        self,
        *,
        max_read_bytes: int | None = None,
        max_write_bytes: int | None = None,
        max_search_results: int | None = None,
        max_list_entries: int | None = None,
        allowed_search_file_patterns: list[str] | None = None,
        source: str = "manual_update",
    ) -> dict[str, Any]:
        with self._lock:
            (
                next_max_read_bytes,
                next_max_write_bytes,
                next_max_search_results,
                next_max_list_entries,
                next_allowed_patterns,
            ) = normalize_file_policy_values(
                max_read_bytes=(
                    int(self._capability_file_policy_max_read_bytes) if max_read_bytes is None else max_read_bytes
                ),
                max_write_bytes=(
                    int(self._capability_file_policy_max_write_bytes) if max_write_bytes is None else max_write_bytes
                ),
                max_search_results=(
                    int(self._capability_file_policy_max_search_results)
                    if max_search_results is None
                    else max_search_results
                ),
                max_list_entries=(
                    int(self._capability_file_policy_max_list_entries) if max_list_entries is None else max_list_entries
                ),
                allowed_search_file_patterns=(
                    list(self._capability_file_policy_allowed_search_file_patterns)
                    if allowed_search_file_patterns is None
                    else allowed_search_file_patterns
                ),
            )
            changed = (
                next_max_read_bytes != self._capability_file_policy_max_read_bytes
                or next_max_write_bytes != self._capability_file_policy_max_write_bytes
                or next_max_search_results != self._capability_file_policy_max_search_results
                or next_max_list_entries != self._capability_file_policy_max_list_entries
                or next_allowed_patterns != self._capability_file_policy_allowed_search_file_patterns
            )
            self._capability_file_policy_max_read_bytes = next_max_read_bytes
            self._capability_file_policy_max_write_bytes = next_max_write_bytes
            self._capability_file_policy_max_search_results = next_max_search_results
            self._capability_file_policy_max_list_entries = next_max_list_entries
            self._capability_file_policy_allowed_search_file_patterns = next_allowed_patterns
            revision = (
                int(self._append_capability_file_policy_history_locked(source=source)["revision"])
                if changed
                else int(self._capability_file_policy_revision)
            )
            return build_file_policy_payload(
                max_read_bytes=int(self._capability_file_policy_max_read_bytes),
                max_write_bytes=int(self._capability_file_policy_max_write_bytes),
                max_search_results=int(self._capability_file_policy_max_search_results),
                max_list_entries=int(self._capability_file_policy_max_list_entries),
                allowed_search_file_patterns=list(self._capability_file_policy_allowed_search_file_patterns),
                revision=revision,
            )

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
            "user_topic_min_score": self._goal_admission_user_topic_min_score,
            "user_topic_defer_score": self._goal_admission_user_topic_defer_score,
            "world_event_min_score": self._goal_admission_world_event_min_score,
            "world_event_defer_score": self._goal_admission_world_event_defer_score,
            "chain_next_min_score": self._goal_admission_chain_next_min_score,
            "chain_next_defer_score": self._goal_admission_chain_next_defer_score,
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
        user_topic_min_score: float | None = None,
        user_topic_defer_score: float | None = None,
        world_event_min_score: float | None = None,
        world_event_defer_score: float | None = None,
        chain_next_min_score: float | None = None,
        chain_next_defer_score: float | None = None,
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
            next_user_min = (
                self._goal_admission_user_topic_min_score
                if user_topic_min_score is None
                else max(0.0, min(1.0, float(user_topic_min_score)))
            )
            next_user_defer = (
                self._goal_admission_user_topic_defer_score
                if user_topic_defer_score is None
                else max(0.0, min(1.0, float(user_topic_defer_score)))
            )
            next_world_min = (
                self._goal_admission_world_event_min_score
                if world_event_min_score is None
                else max(0.0, min(1.0, float(world_event_min_score)))
            )
            next_world_defer = (
                self._goal_admission_world_event_defer_score
                if world_event_defer_score is None
                else max(0.0, min(1.0, float(world_event_defer_score)))
            )
            next_chain_min = (
                self._goal_admission_chain_next_min_score
                if chain_next_min_score is None
                else max(0.0, min(1.0, float(chain_next_min_score)))
            )
            next_chain_defer = (
                self._goal_admission_chain_next_defer_score
                if chain_next_defer_score is None
                else max(0.0, min(1.0, float(chain_next_defer_score)))
            )
            if next_danger > next_warning:
                raise ValueError("stability_danger_rate must be <= stability_warning_rate")
            if next_user_defer > next_user_min:
                raise ValueError("user_topic_defer_score must be <= user_topic_min_score")
            if next_world_defer > next_world_min:
                raise ValueError("world_event_defer_score must be <= world_event_min_score")
            if next_chain_defer > next_chain_min:
                raise ValueError("chain_next_defer_score must be <= chain_next_min_score")
            changed = (
                next_warning != self._goal_admission_stability_warning_rate
                or next_danger != self._goal_admission_stability_danger_rate
                or next_user_min != self._goal_admission_user_topic_min_score
                or next_user_defer != self._goal_admission_user_topic_defer_score
                or next_world_min != self._goal_admission_world_event_min_score
                or next_world_defer != self._goal_admission_world_event_defer_score
                or next_chain_min != self._goal_admission_chain_next_min_score
                or next_chain_defer != self._goal_admission_chain_next_defer_score
            )
            self._goal_admission_stability_warning_rate = next_warning
            self._goal_admission_stability_danger_rate = next_danger
            self._goal_admission_user_topic_min_score = next_user_min
            self._goal_admission_user_topic_defer_score = next_user_defer
            self._goal_admission_world_event_min_score = next_world_min
            self._goal_admission_world_event_defer_score = next_world_defer
            self._goal_admission_chain_next_min_score = next_chain_min
            self._goal_admission_chain_next_defer_score = next_chain_defer
            if changed:
                revision = int(self._append_goal_admission_history_locked(source=source)["revision"])
            else:
                revision = int(self._goal_admission_config_revision)
            return {
                "stability_warning_rate": self._goal_admission_stability_warning_rate,
                "stability_danger_rate": self._goal_admission_stability_danger_rate,
                "user_topic_min_score": self._goal_admission_user_topic_min_score,
                "user_topic_defer_score": self._goal_admission_user_topic_defer_score,
                "world_event_min_score": self._goal_admission_world_event_min_score,
                "world_event_defer_score": self._goal_admission_world_event_defer_score,
                "chain_next_min_score": self._goal_admission_chain_next_min_score,
                "chain_next_defer_score": self._goal_admission_chain_next_defer_score,
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
            self._goal_admission_user_topic_min_score = float(previous_entry["user_topic_min_score"])
            self._goal_admission_user_topic_defer_score = float(previous_entry["user_topic_defer_score"])
            self._goal_admission_world_event_min_score = float(previous_entry["world_event_min_score"])
            self._goal_admission_world_event_defer_score = float(previous_entry["world_event_defer_score"])
            self._goal_admission_chain_next_min_score = float(previous_entry["chain_next_min_score"])
            self._goal_admission_chain_next_defer_score = float(previous_entry["chain_next_defer_score"])
            history_entry = self._append_goal_admission_history_locked(
                source="rollback",
                rolled_back_from_revision=rolled_back_from_revision,
            )
            return {
                "stability_warning_rate": self._goal_admission_stability_warning_rate,
                "stability_danger_rate": self._goal_admission_stability_danger_rate,
                "user_topic_min_score": self._goal_admission_user_topic_min_score,
                "user_topic_defer_score": self._goal_admission_user_topic_defer_score,
                "world_event_min_score": self._goal_admission_world_event_min_score,
                "world_event_defer_score": self._goal_admission_world_event_defer_score,
                "chain_next_min_score": self._goal_admission_chain_next_min_score,
                "chain_next_defer_score": self._goal_admission_chain_next_defer_score,
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
