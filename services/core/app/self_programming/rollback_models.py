from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class RollbackReason(str, Enum):
    """触发回滚的原因。"""

    VERIFICATION_FAILED = "verification_failed"
    HEALTH_DEGRADED = "health_degraded"
    MANUAL_REQUEST = "manual_request"
    CASCADE_DEPENDENCY = "cascade_dependency"
    SANDBOX_MISMATCH = "sandbox_mismatch"


class RollbackStatus(str, Enum):
    """回滚操作状态。"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class DiffSnapshot:
    """单个文件的修改前后快照。"""

    file_path: str
    original_content: str
    original_hash: str
    timestamp: str = ""
    file_existed: bool = True

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", datetime.now(timezone.utc).isoformat())

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.original_content.encode("utf-8")).hexdigest()

    @classmethod
    def from_path(cls, file_path: str | Path, workspace_root: Path) -> "DiffSnapshot":
        rel_path = Path(file_path).as_posix()
        if Path(file_path).is_absolute():
            try:
                rel_path = Path(file_path).relative_to(workspace_root).as_posix()
            except ValueError:
                pass

        full_path = workspace_root / rel_path
        if full_path.exists():
            content = full_path.read_text(encoding="utf-8")
            return cls(
                file_path=rel_path,
                original_content=content,
                original_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                file_existed=True,
            )
        return cls(
            file_path=rel_path,
            original_content="",
            original_hash="",
            file_existed=False,
        )


@dataclass
class RollbackPlan:
    """回滚计划。"""

    job_id: str
    reason: RollbackReason
    reason_detail: str = ""
    snapshots: list[DiffSnapshot] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    dependent_job_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.affected_files and self.snapshots:
            self.affected_files = [s.file_path for s in self.snapshots]

    @property
    def summary(self) -> str:
        emoji_map = {
            RollbackReason.VERIFICATION_FAILED: "🔴",
            RollbackReason.HEALTH_DEGRADED: "📉",
            RollbackReason.MANUAL_REQUEST: "👤",
            RollbackReason.CASCADE_DEPENDENCY: "🔗",
            RollbackReason.SANDBOX_MISMATCH: "⚠️",
        }
        emoji = emoji_map.get(self.reason, "🔄")
        dep_note = f", 级联影响 {len(self.dependent_job_ids)} 个后续 Job" if self.dependent_job_ids else ""
        return f"{emoji} 回滚计划 [{self.job_id[:12]}]: {self.reason.value}{dep_note}, 影响 {len(self.affected_files)} 个文件"


@dataclass
class RollbackResult:
    """回滚执行结果。"""

    status: RollbackStatus
    plan: RollbackPlan
    restored_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    verification_passed: bool | None = None
    verification_output: str = ""
    duration_seconds: float = 0.0
    rolled_back_at: str = ""
    recommendation: str = ""

    def __post_init__(self) -> None:
        if not self.rolled_back_at and self.status != RollbackStatus.SKIPPED:
            object.__setattr__(self, "rolled_back_at", datetime.now(timezone.utc).isoformat())

    @property
    def summary(self) -> str:
        status_emoji = {
            RollbackStatus.SUCCESS: "✅",
            RollbackStatus.PARTIAL: "⚠️",
            RollbackStatus.FAILED: "❌",
            RollbackStatus.SKIPPED: "➡️",
        }
        emoji = status_emoji.get(self.status, "?")
        parts = [f"{emoji} 回滚 {self.status.value}"]
        if self.restored_files:
            parts.append(f"还原 {len(self.restored_files)} 文件")
        if self.failed_files:
            parts.append(f"失败 {len(self.failed_files)} 文件")
        if self.verification_passed is True:
            parts.append("验证通过 ✓")
        elif self.verification_passed is False:
            parts.append("验证未通过 ✗")
        return " | ".join(parts)

