from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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

CAPABILITY_POLICY_HISTORY_MAX_ENTRIES = 50


class CapabilityPolicyState:
    def initialize(self, owner: Any) -> None:
        owner._capability_shell_policy_revision = 0
        owner._capability_shell_policy_allowed_executables = list(DEFAULT_ALLOWED_EXECUTABLES)
        owner._capability_shell_policy_allowed_git_subcommands = list(DEFAULT_ALLOWED_GIT_SUBCOMMANDS)
        owner._capability_shell_policy_history = []
        self.append_shell_history(owner, source="bootstrap")

        owner._capability_file_policy_revision = 0
        owner._capability_file_policy_max_read_bytes = DEFAULT_MAX_READ_BYTES
        owner._capability_file_policy_max_write_bytes = DEFAULT_MAX_WRITE_BYTES
        owner._capability_file_policy_max_search_results = DEFAULT_MAX_SEARCH_RESULTS
        owner._capability_file_policy_max_list_entries = DEFAULT_MAX_LIST_ENTRIES
        owner._capability_file_policy_allowed_search_file_patterns = list(DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS)
        owner._capability_file_policy_history = []
        self.append_file_history(owner, source="bootstrap")

    def ensure_fields(self, owner: Any) -> None:
        if not hasattr(owner, "_capability_shell_policy_revision"):
            owner._capability_shell_policy_revision = 0
        if not hasattr(owner, "_capability_shell_policy_allowed_executables") or not isinstance(
            owner._capability_shell_policy_allowed_executables,
            list,
        ):
            owner._capability_shell_policy_allowed_executables = list(DEFAULT_ALLOWED_EXECUTABLES)
        if not hasattr(owner, "_capability_shell_policy_allowed_git_subcommands") or not isinstance(
            owner._capability_shell_policy_allowed_git_subcommands,
            list,
        ):
            owner._capability_shell_policy_allowed_git_subcommands = list(DEFAULT_ALLOWED_GIT_SUBCOMMANDS)
        if not hasattr(owner, "_capability_shell_policy_history") or not isinstance(
            owner._capability_shell_policy_history,
            list,
        ):
            owner._capability_shell_policy_history = []
        if not owner._capability_shell_policy_history:
            self.append_shell_history(owner, source="bootstrap")

        if not hasattr(owner, "_capability_file_policy_revision"):
            owner._capability_file_policy_revision = 0
        if not hasattr(owner, "_capability_file_policy_max_read_bytes"):
            owner._capability_file_policy_max_read_bytes = DEFAULT_MAX_READ_BYTES
        if not hasattr(owner, "_capability_file_policy_max_write_bytes"):
            owner._capability_file_policy_max_write_bytes = DEFAULT_MAX_WRITE_BYTES
        if not hasattr(owner, "_capability_file_policy_max_search_results"):
            owner._capability_file_policy_max_search_results = DEFAULT_MAX_SEARCH_RESULTS
        if not hasattr(owner, "_capability_file_policy_max_list_entries"):
            owner._capability_file_policy_max_list_entries = DEFAULT_MAX_LIST_ENTRIES
        if not hasattr(owner, "_capability_file_policy_allowed_search_file_patterns") or not isinstance(
            owner._capability_file_policy_allowed_search_file_patterns,
            list,
        ):
            owner._capability_file_policy_allowed_search_file_patterns = list(DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS)
        if not hasattr(owner, "_capability_file_policy_history") or not isinstance(
            owner._capability_file_policy_history,
            list,
        ):
            owner._capability_file_policy_history = []
        if not owner._capability_file_policy_history:
            self.append_file_history(owner, source="bootstrap")

    def append_shell_history(self, owner: Any, *, source: str) -> dict[str, Any]:
        owner._capability_shell_policy_revision += 1
        entry = {
            "revision": owner._capability_shell_policy_revision,
            "source": source,
            "version": SHELL_POLICY_VERSION,
            "allowed_executables": list(owner._capability_shell_policy_allowed_executables),
            "allowed_git_subcommands": list(owner._capability_shell_policy_allowed_git_subcommands),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        owner._capability_shell_policy_history.append(entry)
        if len(owner._capability_shell_policy_history) > CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            owner._capability_shell_policy_history = owner._capability_shell_policy_history[
                -CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            ]
        return dict(entry)

    def list_shell_history(self, owner: Any, *, limit: int) -> list[dict[str, Any]]:
        requested = max(1, min(CAPABILITY_POLICY_HISTORY_MAX_ENTRIES, int(limit)))
        snapshot = [dict(item) for item in owner._capability_shell_policy_history[-requested:]]
        return list(reversed(snapshot))

    def get_shell_policy(self, owner: Any) -> dict[str, Any]:
        return build_shell_policy_payload(
            allowed_executables=list(owner._capability_shell_policy_allowed_executables),
            allowed_git_subcommands=list(owner._capability_shell_policy_allowed_git_subcommands),
            revision=int(owner._capability_shell_policy_revision),
        )

    def update_shell_policy(
        self,
        owner: Any,
        *,
        allowed_executables: list[str] | None,
        allowed_git_subcommands: list[str] | None,
        source: str,
    ) -> dict[str, Any]:
        next_executables, next_git_subcommands = normalize_shell_policy_values(
            allowed_executables=(
                list(owner._capability_shell_policy_allowed_executables)
                if allowed_executables is None
                else allowed_executables
            ),
            allowed_git_subcommands=(
                list(owner._capability_shell_policy_allowed_git_subcommands)
                if allowed_git_subcommands is None
                else allowed_git_subcommands
            ),
        )
        changed = (
            next_executables != owner._capability_shell_policy_allowed_executables
            or next_git_subcommands != owner._capability_shell_policy_allowed_git_subcommands
        )
        owner._capability_shell_policy_allowed_executables = next_executables
        owner._capability_shell_policy_allowed_git_subcommands = next_git_subcommands
        revision = (
            int(self.append_shell_history(owner, source=source)["revision"])
            if changed
            else int(owner._capability_shell_policy_revision)
        )
        return build_shell_policy_payload(
            allowed_executables=list(owner._capability_shell_policy_allowed_executables),
            allowed_git_subcommands=list(owner._capability_shell_policy_allowed_git_subcommands),
            revision=revision,
        )

    def append_file_history(self, owner: Any, *, source: str) -> dict[str, Any]:
        owner._capability_file_policy_revision += 1
        entry = {
            "revision": owner._capability_file_policy_revision,
            "source": source,
            "version": FILE_POLICY_VERSION,
            "max_read_bytes": owner._capability_file_policy_max_read_bytes,
            "max_write_bytes": owner._capability_file_policy_max_write_bytes,
            "max_search_results": owner._capability_file_policy_max_search_results,
            "max_list_entries": owner._capability_file_policy_max_list_entries,
            "allowed_search_file_patterns": list(owner._capability_file_policy_allowed_search_file_patterns),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        owner._capability_file_policy_history.append(entry)
        if len(owner._capability_file_policy_history) > CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            owner._capability_file_policy_history = owner._capability_file_policy_history[
                -CAPABILITY_POLICY_HISTORY_MAX_ENTRIES:
            ]
        return dict(entry)

    def list_file_history(self, owner: Any, *, limit: int) -> list[dict[str, Any]]:
        requested = max(1, min(CAPABILITY_POLICY_HISTORY_MAX_ENTRIES, int(limit)))
        snapshot = [dict(item) for item in owner._capability_file_policy_history[-requested:]]
        return list(reversed(snapshot))

    def get_file_policy(self, owner: Any) -> dict[str, Any]:
        return build_file_policy_payload(
            max_read_bytes=int(owner._capability_file_policy_max_read_bytes),
            max_write_bytes=int(owner._capability_file_policy_max_write_bytes),
            max_search_results=int(owner._capability_file_policy_max_search_results),
            max_list_entries=int(owner._capability_file_policy_max_list_entries),
            allowed_search_file_patterns=list(owner._capability_file_policy_allowed_search_file_patterns),
            revision=int(owner._capability_file_policy_revision),
        )

    def update_file_policy(
        self,
        owner: Any,
        *,
        max_read_bytes: int | None,
        max_write_bytes: int | None,
        max_search_results: int | None,
        max_list_entries: int | None,
        allowed_search_file_patterns: list[str] | None,
        source: str,
    ) -> dict[str, Any]:
        (
            next_max_read_bytes,
            next_max_write_bytes,
            next_max_search_results,
            next_max_list_entries,
            next_allowed_patterns,
        ) = normalize_file_policy_values(
            max_read_bytes=int(owner._capability_file_policy_max_read_bytes) if max_read_bytes is None else max_read_bytes,
            max_write_bytes=int(owner._capability_file_policy_max_write_bytes) if max_write_bytes is None else max_write_bytes,
            max_search_results=(
                int(owner._capability_file_policy_max_search_results)
                if max_search_results is None
                else max_search_results
            ),
            max_list_entries=(
                int(owner._capability_file_policy_max_list_entries)
                if max_list_entries is None
                else max_list_entries
            ),
            allowed_search_file_patterns=(
                list(owner._capability_file_policy_allowed_search_file_patterns)
                if allowed_search_file_patterns is None
                else allowed_search_file_patterns
            ),
        )
        changed = (
            next_max_read_bytes != owner._capability_file_policy_max_read_bytes
            or next_max_write_bytes != owner._capability_file_policy_max_write_bytes
            or next_max_search_results != owner._capability_file_policy_max_search_results
            or next_max_list_entries != owner._capability_file_policy_max_list_entries
            or next_allowed_patterns != owner._capability_file_policy_allowed_search_file_patterns
        )
        owner._capability_file_policy_max_read_bytes = next_max_read_bytes
        owner._capability_file_policy_max_write_bytes = next_max_write_bytes
        owner._capability_file_policy_max_search_results = next_max_search_results
        owner._capability_file_policy_max_list_entries = next_max_list_entries
        owner._capability_file_policy_allowed_search_file_patterns = next_allowed_patterns
        revision = (
            int(self.append_file_history(owner, source=source)["revision"])
            if changed
            else int(owner._capability_file_policy_revision)
        )
        return build_file_policy_payload(
            max_read_bytes=int(owner._capability_file_policy_max_read_bytes),
            max_write_bytes=int(owner._capability_file_policy_max_write_bytes),
            max_search_results=int(owner._capability_file_policy_max_search_results),
            max_list_entries=int(owner._capability_file_policy_max_list_entries),
            allowed_search_file_patterns=list(owner._capability_file_policy_allowed_search_file_patterns),
            revision=revision,
        )
