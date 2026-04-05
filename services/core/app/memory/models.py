"""记忆数据模型

设计理念：
- 记忆不是扁平的事件流，而是有类型、重要性、情绪色彩的结构化数据
- 不同类型的记忆有不同的生命周期和检索策略
- 记忆与人格系统深度耦合：性格影响记忆偏好，记忆反过来塑造人格演化

记忆类型：
1. fact       — 事实记忆（用户偏好、重要约定、关键信息）
2. episodic   — 情景记忆（某次对话的氛围、共同经历的片段）
3. semantic   — 知识记忆（学到的概念、技能、理解）
4. emotional  — 情绪印记（强烈情绪事件的记录）
5. chat_raw   — 原始对话（完整聊天记录，用于上下文）

记忆强度（从弱到强）：
  faint → weak → normal → vivid → core
  core 级别的记忆几乎不会被遗忘
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ── 枚举类型 ──────────────────────────────────────────────


class MemoryKind(str, Enum):
    """记忆类型"""
    FACT = "fact"             # 事实：用户喜欢咖啡、明天3点开会
    EPISODIC = "episodic"     # 情景：上次聊到深夜、那次一起调试bug
    SEMANTIC = "semantic"     # 知识：学会了pytest的fixture用法
    EMOTIONAL = "emotional"   # 情绪印记：用户生气时提到过...
    CHAT_RAW = "chat_raw"     # 原始对话：完整的聊天记录


class MemoryStrength(str, Enum):
    """记忆强度 — 越强越不容易被淡化/遗忘"""
    FAINT = "faint"           # 模糊，随时可能忘记 (0)
    WEAK = "weak"             # 弱记得，偶尔能想起来 (1)
    NORMAL = "normal"         # 正常记忆 (2)
    VIVID = "vivid"           # 鲜明，印象很深 (3)
    CORE = "core"             # 核心记忆，几乎不会忘 (4)


class MemoryEmotion(str, Enum):
    """记忆的情绪标签"""
    POSITIVE = "positive"     # 正面
    NEGATIVE = "negative"     # 负面
    NEUTRAL = "neutral"       # 中性
    MIXED = "mixed"           # 复杂/混合


# ── 核心数据模型 ──────────────────────────────────────────


class MemoryEntry(BaseModel):
    """单条记忆条目。"""
    id: str = Field(default_factory=lambda: _generate_id(), description="唯一 ID")
    kind: MemoryKind = MemoryKind.CHAT_RAW
    content: str = Field(min_length=1, description="记忆内容")
    role: str | None = Field(default=None, description="说话人角色（仅 chat_raw 使用）")

    # ── 强度与生命周期 ──
    strength: MemoryStrength = MemoryStrength.NORMAL
    importance: int = Field(default=5, ge=0, le=10, description="重要性 0-10")
    access_count: int = Field(default=0, ge=0, description="被检索/回忆的次数")

    # ── 元数据 ──
    emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    subject: str | None = Field(default=None, description="相关主体/实体")
    source_context: str | None = Field(default=None, description="来源上下文摘要")

    # ── 时间戳 ──
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime | None = Field(default=None, description="最后访问时间")
    expires_at: datetime | None = Field(default=None, description="过期时间（可选）")

    # ── 关联 ──
    related_memory_ids: list[str] = Field(
        default_factory=list,
        description="关联的其他记忆 ID",
    )

    @classmethod
    def create(
        cls,
        *,
        kind: MemoryKind,
        content: str,
        role: str | None = None,
        strength: MemoryStrength = MemoryStrength.NORMAL,
        importance: int = 5,
        emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL,
        keywords: list[str] | None = None,
        subject: str | None = None,
        source_context: str | None = None,
    ) -> "MemoryEntry":
        """统一的显式构造入口，避免调用方散落直接拼字段。"""
        return cls(
            kind=kind,
            content=content,
            role=role,
            strength=strength,
            importance=importance,
            emotion_tag=emotion_tag,
            keywords=keywords or [],
            subject=subject,
            source_context=source_context,
        )

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def retention_score(self) -> float:
        """保留分值 0~1 — 越高越不容易被清理

        计算：基础强度 + 重要性加权 + 访问频率加成
        """
        strength_map = {
            MemoryStrength.FAINT: 0.1,
            MemoryStrength.WEAK: 0.3,
            MemoryStrength.NORMAL: 0.55,
            MemoryStrength.VIVID: 0.8,
            MemoryStrength.CORE: 1.0,
        }
        base = strength_map.get(self.strength, 0.5)

        # 重要性加成 (0~0.2)
        importance_bonus = (self.importance / 10) * 0.2

        # 访问频率加成（对数衰减，避免无限增长）
        access_bonus = min(0.15, (self.access_count ** 0.5) * 0.03)

        return round(min(1.0, base + importance_bonus + access_bonus), 3)

    def to_prompt_fragment(self) -> str:
        """将记忆转为 prompt 片段（注入到 system prompt 中）"""
        kind_label = {
            MemoryKind.FACT: "事实",
            MemoryKind.EPISODIC: "经历",
            MemoryKind.SEMANTIC: "知识",
            MemoryKind.EMOTIONAL: "情绪印记",
            MemoryKind.CHAT_RAW: "对话",
        }

        label = kind_label.get(self.kind.value, "记忆")
        prefix = f"[{label}]"

        if self.subject:
            prefix += f"（关于 {self.subject}）"
        if self.role:
            prefix += f" [{self.role}]"

        return f"{prefix} {self.content}"

    def to_display_dict(self) -> dict:
        """转为界面使用的字典。"""
        return {
            "id": self.id,  # 返回完整 ID 确保唯一性
            "kind": self.kind.value,
            "content": self.content,
            "role": self.role,
            "strength": self.strength.value,
            "importance": self.importance,
            "emotion_tag": self.emotion_tag.value,
            "subject": self.subject,
            "keywords": self.keywords,
            "retention_score": round(self.retention_score * 100),
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
        }


# ── 记忆集合 / 视图 ─────────────────────────────────────


class MemoryCollection(BaseModel):
    """一组记忆的集合视图（用于返回给调用方）"""

    entries: list[MemoryEntry] = Field(default_factory=list)
    total_count: int = 0
    query_summary: str | None = None

    @property
    def has_facts(self) -> bool:
        return any(e.kind == MemoryKind.FACT for e in self.entries)

    @property
    def has_episodic(self) -> bool:
        return any(e.kind == MemoryKind.EPISODIC for e in self.entries)

    def filter_by_kind(self, *kinds: MemoryKind) -> "MemoryCollection":
        """按类型过滤"""
        filtered = [e for e in self.entries if e.kind in kinds]
        return MemoryCollection(
            entries=filtered,
            total_count=len(filtered),
            query_summary=self.query_summary,
        )

    def get_top_by_importance(self, n: int = 5) -> list[MemoryEntry]:
        """获取最重要的 n 条"""
        sorted_entries = sorted(self.entries, key=lambda e: e.importance, reverse=True)
        return sorted_entries[:n]

    def get_recent(self, n: int = 10) -> list[MemoryEntry]:
        """获取最近的 n 条"""
        sorted_entries = sorted(self.entries, key=lambda e: e.created_at, reverse=True)
        return sorted_entries[:n]

    def to_prompt_context(self, max_chars: int = 800) -> str:
        """将记忆集合转为 prompt 上下文字符串

        策略：
        1. 优先包含 CORE/VIVID 级别记忆
        2. 按 kind 分组，每组取最重要的几条
        3. 总字符数不超过 max_chars
        """
        sorted_entries = sorted(
            self.entries,
            key=lambda e: (e.retention_score, e.importance),
            reverse=True,
        )

        fragments: list[str] = []
        total_chars = 0

        for entry in sorted_entries:
            frag = entry.to_prompt_fragment()
            if total_chars + len(frag) + 1 > max_chars:
                break
            fragments.append(frag)
            total_chars += len(frag) + 1

        if not fragments:
            return ""

        return "\n".join(fragments)


# ── 存储事件模型 ────────────────────────────────────────


class MemoryEvent(BaseModel):
    """记忆存储层使用的事件模型。"""
    kind: str
    content: str
    role: str | None = None
    source_context: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entry_id: str = Field(
        default_factory=lambda: _generate_id(),
        description="关联的 MemoryEntry ID（用于删除/更新匹配）",
    )

    @classmethod
    def from_entry(cls, entry: MemoryEntry) -> "MemoryEvent":
        """从 MemoryEntry 转换到存储事件。"""
        return cls(
            kind=_storage_kind_for_entry(entry),
            content=entry.content,
            role=entry.role,
            source_context=entry.source_context,
            created_at=entry.created_at,
            entry_id=entry.id,  # 保存 ID 用于后续匹配
        )

    def to_entry(self) -> MemoryEntry:
        """从存储事件转换为 MemoryEntry。"""
        kind_map = {
            "chat": MemoryKind.CHAT_RAW,
            "world": MemoryKind.FACT,
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
            MemoryKind.FACT: 6,          # 事实默认较重要
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
            source_context=self.source_context,
            created_at=self.created_at,
            importance=default_importance,
        )


# ── 辅助函数 ─────────────────────────────────────────────


_counter = 0


def _generate_id(length: int = 12) -> str:
    """生成短 ID（基于时间戳+计数器，不需要 uuid 那么长）"""
    global _counter
    _counter += 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"mem_{ts}_{_counter:x}"


def _storage_kind_for_entry(entry: MemoryEntry) -> str:
    """将 MemoryEntry 映射到存储层事件类型，保留运行时依赖的子类型。"""
    if entry.source_context in {"world", "inner", "autobio", "action", "self_check", "assistant_note"}:
        return entry.source_context

    if entry.kind == MemoryKind.CHAT_RAW and entry.role in {"user", "assistant"}:
        return "chat"

    return entry.kind.value
