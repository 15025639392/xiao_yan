from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommitInfo:
    """Git commit 的元信息。"""

    hash: str = ""
    branch: str = ""
    message: str = ""
    short_hash: str = ""
    files_changed: list[str] = field(default_factory=list)
    committed_at: str = ""


@dataclass
class GitStatus:
    """当前工作区 Git 状态快照。"""

    is_git_repo: bool = False
    current_branch: str = ""
    is_clean: bool = True
    staged_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)


__all__ = [
    "CommitInfo",
    "GitStatus",
]
