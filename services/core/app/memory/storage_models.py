from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


_counter = 0
_ALLOWED_MEMORY_NAMESPACES = {"chat", "autobio", "inner", "long_term"}


def generate_memory_id(length: int = 12) -> str:
    """生成短 ID（基于时间戳+计数器，不需要 uuid 那么长）"""
    _ = length
    global _counter
    _counter += 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"mem_{ts}_{_counter:x}"


def storage_kind_for_entry(entry) -> str:
    """将 MemoryEntry 映射到存储层事件类型，保留运行时依赖的子类型。"""
    if entry.source_context in {"world", "inner", "autobio", "action", "self_check", "assistant_note"}:
        return entry.source_context

    if entry.kind.value == "chat_raw" and entry.role in {"user", "assistant"}:
        return "chat"

    return entry.kind.value


def default_namespace_for_kind(kind: str) -> str:
    normalized_kind = (kind or "").strip().lower()
    if normalized_kind in {"autobio"}:
        return "autobio"
    if normalized_kind in {"inner", "world", "action", "self_check"}:
        return "inner"
    if normalized_kind in {"semantic", "fact", "emotional", "episodic"}:
        return "long_term"
    return "chat"


class MemoryEvent(BaseModel):
    """记忆存储层使用的事件模型。"""

    kind: str
    content: str
    role: str | None = None
    session_id: str | None = None
    request_key: str | None = Field(default=None, description="前后端请求关联键")
    source_context: str | None = None
    reasoning_session_id: str | None = Field(default=None, description="持续推理会话 ID")
    reasoning_state: dict[str, Any] | None = Field(default=None, description="持续推理状态快照")
    namespace: str | None = Field(default=None, description="记忆命名空间：chat/autobio/inner/long_term")
    facet: str | None = Field(default=None, description="记忆分类标签，如 preference/habit/profile_fact")
    tags: list[str] = Field(default_factory=list, description="记忆标签")
    source_ref: str | None = Field(default=None, description="记忆来源引用（文件、URL、会话片段）")
    version_tag: str | None = Field(default=None, description="记忆版本标签")
    governance_source: Literal["system", "auto_extracted", "manual"] = Field(
        default="system",
        description="记忆治理来源：system/auto_extracted/manual",
    )
    review_status: Literal["pending_review", "approved", "rejected"] = Field(
        default="approved",
        description="记忆审核状态",
    )
    reviewed_by: str | None = Field(default=None, description="审核人")
    reviewed_at: datetime | None = Field(default=None, description="审核时间")
    review_note: str | None = Field(default=None, description="审核备注")
    visibility: Literal["internal", "user"] = Field(
        default="internal",
        description="可见性：internal=系统内部，user=对用户可见",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = Field(default=None, description="软删除时间")
    entry_id: str = Field(
        default_factory=lambda: generate_memory_id(),
        description="关联的 MemoryEntry ID（用于删除/更新匹配）",
    )
    related_memory_ids: list[str] = Field(
        default_factory=list,
        description="关联的其他记忆 ID",
    )

    @classmethod
    def from_entry(cls, entry) -> "MemoryEvent":
        """从 MemoryEntry 转换到存储事件。"""
        from app.memory.models import MemoryKind

        storage_kind = storage_kind_for_entry(entry)
        return cls(
            kind=storage_kind,
            content=entry.content,
            role=entry.role,
            session_id=entry.session_id,
            source_context=entry.source_context,
            namespace=default_namespace_for_kind(storage_kind),
            facet="semantic" if entry.kind == MemoryKind.SEMANTIC else None,
            source_ref=entry.source_context,
            created_at=entry.created_at,
            deleted_at=entry.deleted_at,
            entry_id=entry.id,
        )

    @model_validator(mode="after")
    def _normalize_memory_schema(self) -> "MemoryEvent":
        normalized_namespace = (self.namespace or "").strip().lower()
        if not normalized_namespace:
            normalized_namespace = default_namespace_for_kind(self.kind)
        if normalized_namespace not in _ALLOWED_MEMORY_NAMESPACES:
            allowed = ", ".join(sorted(_ALLOWED_MEMORY_NAMESPACES))
            raise ValueError(f"namespace must be one of: {allowed}")
        self.namespace = normalized_namespace

        if self.facet is not None:
            normalized_facet = self.facet.strip()
            self.facet = normalized_facet or None

        normalized_tags: list[str] = []
        for raw_tag in self.tags or []:
            normalized_tag = str(raw_tag).strip().lower()
            if normalized_tag and normalized_tag not in normalized_tags:
                normalized_tags.append(normalized_tag)
        self.tags = normalized_tags

        if self.source_ref is not None:
            normalized_source_ref = self.source_ref.strip()
            self.source_ref = normalized_source_ref or None

        if self.version_tag is not None:
            normalized_version_tag = self.version_tag.strip()
            self.version_tag = normalized_version_tag or None

        if self.reviewed_by is not None:
            normalized_reviewed_by = self.reviewed_by.strip()
            self.reviewed_by = normalized_reviewed_by or None

        if self.review_note is not None:
            normalized_review_note = self.review_note.strip()
            self.review_note = normalized_review_note or None

        if self.reasoning_session_id is not None:
            normalized_reasoning_session_id = self.reasoning_session_id.strip()
            self.reasoning_session_id = normalized_reasoning_session_id or None

        if self.request_key is not None:
            normalized_request_key = self.request_key.strip()
            self.request_key = normalized_request_key or None

        if self.reasoning_state is not None:
            if not isinstance(self.reasoning_state, dict):
                self.reasoning_state = None
            else:
                normalized_reasoning_state = dict(self.reasoning_state)
                raw_reasoning_state_session_id = normalized_reasoning_state.get("session_id")
                if isinstance(raw_reasoning_state_session_id, str):
                    normalized_state_session_id = raw_reasoning_state_session_id.strip()
                    if normalized_state_session_id:
                        normalized_reasoning_state["session_id"] = normalized_state_session_id
                    else:
                        normalized_reasoning_state.pop("session_id", None)
                self.reasoning_state = normalized_reasoning_state
                if self.reasoning_session_id is None:
                    candidate_session_id = normalized_reasoning_state.get("session_id")
                    if isinstance(candidate_session_id, str) and candidate_session_id.strip():
                        self.reasoning_session_id = candidate_session_id.strip()

        return self

    def to_entry(self):
        """从存储事件转换为 MemoryEntry。"""
        from app.memory.models import MemoryEntry, MemoryKind

        kind_map = {
            "chat": MemoryKind.CHAT_RAW,
            "world": MemoryKind.EPISODIC,
            "inner": MemoryKind.EPISODIC,
            "autobio": MemoryKind.EPISODIC,
            "action": MemoryKind.EPISODIC,
            "self_check": MemoryKind.EPISODIC,
            "assistant_note": MemoryKind.CHAT_RAW,
            "fact": MemoryKind.FACT,
            "episodic": MemoryKind.EPISODIC,
            "semantic": MemoryKind.SEMANTIC,
            "emotional": MemoryKind.EMOTIONAL,
            "chat_raw": MemoryKind.CHAT_RAW,
        }
        kind = kind_map.get(self.kind, MemoryKind.CHAT_RAW)

        default_importance = {
            MemoryKind.FACT: 6,
            MemoryKind.EMOTIONAL: 5,
            MemoryKind.EPISODIC: 4,
            MemoryKind.SEMANTIC: 5,
            MemoryKind.CHAT_RAW: 2,
        }.get(kind, 5)

        return MemoryEntry(
            id=self.entry_id,
            kind=kind,
            content=self.content,
            role=self.role,
            session_id=self.session_id,
            source_context=self.source_context,
            created_at=self.created_at,
            deleted_at=self.deleted_at,
            importance=default_importance,
            related_memory_ids=self.related_memory_ids,
        )
