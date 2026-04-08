from __future__ import annotations

import re

SHELL_POLICY_VERSION = "2026-04-08-v1"

DEFAULT_ALLOWED_EXECUTABLES: tuple[str, ...] = (
    "pwd",
    "date",
    "echo",
    "whoami",
    "hostname",
    "uname",
    "uptime",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "diff",
    "tree",
    "file",
    "du",
    "df",
    "stat",
    "readlink",
    "basename",
    "dirname",
    "realpath",
    "find",
    "grep",
    "git",
)

DEFAULT_ALLOWED_GIT_SUBCOMMANDS: tuple[str, ...] = (
    "status",
    "log",
    "diff",
    "show",
    "branch",
    "rev-parse",
    "remote",
    "describe",
)

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_ALLOWED_EXECUTABLES_SET = set(DEFAULT_ALLOWED_EXECUTABLES)
_ALLOWED_GIT_SUBCOMMANDS_SET = set(DEFAULT_ALLOWED_GIT_SUBCOMMANDS)


def _normalize_token_list(
    raw_values: list[str] | tuple[str, ...] | None,
    *,
    defaults: tuple[str, ...],
    allowed_set: set[str],
    field_name: str,
) -> list[str]:
    if raw_values is None:
        return list(defaults)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        value = raw.strip()
        if not value:
            continue
        if value in seen:
            continue
        if not _TOKEN_PATTERN.fullmatch(value):
            raise ValueError(f"{field_name} contains invalid token: {value}")
        if value not in allowed_set:
            raise ValueError(f"{field_name} contains unsupported value: {value}")
        seen.add(value)
        normalized.append(value)

    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def normalize_shell_policy_values(
    *,
    allowed_executables: list[str] | tuple[str, ...] | None = None,
    allowed_git_subcommands: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[str], list[str]]:
    executables = _normalize_token_list(
        allowed_executables,
        defaults=DEFAULT_ALLOWED_EXECUTABLES,
        allowed_set=_ALLOWED_EXECUTABLES_SET,
        field_name="allowed_executables",
    )
    git_subcommands = _normalize_token_list(
        allowed_git_subcommands,
        defaults=DEFAULT_ALLOWED_GIT_SUBCOMMANDS,
        allowed_set=_ALLOWED_GIT_SUBCOMMANDS_SET,
        field_name="allowed_git_subcommands",
    )
    if "git" not in executables and git_subcommands:
        raise ValueError("allowed_git_subcommands requires 'git' in allowed_executables")
    return executables, git_subcommands


def build_shell_policy_payload(
    *,
    allowed_executables: list[str] | tuple[str, ...] | None = None,
    allowed_git_subcommands: list[str] | tuple[str, ...] | None = None,
    revision: int | None = None,
) -> dict:
    executables, git_subcommands = normalize_shell_policy_values(
        allowed_executables=allowed_executables,
        allowed_git_subcommands=allowed_git_subcommands,
    )
    payload = {
        "version": SHELL_POLICY_VERSION,
        "allowed_executables": executables,
        "allowed_git_subcommands": git_subcommands,
    }
    if revision is not None:
        payload["revision"] = int(revision)
    return payload
