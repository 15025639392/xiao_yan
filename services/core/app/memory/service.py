"""MemoryService — 记忆与人格联动服务

核心目标：将记忆从"扁平事件流"升级为"有生命的记忆系统"

职责：
1. 记忆 CRUD（创建/读取/更新/删除）
2. 对话后自动提取关键信息存为记忆
3. 人格感知的记忆检索（性格影响检索偏好）
4. 记忆生命周期管理（淡化/强化/过期清理）
5. 生成 prompt 注入用的记忆上下文

设计原则：
- 性格影响记忆：高开放性的人记住更多新奇事物，高神经质的人更容易记住负面情绪
- 使用驱动强化：被频繁回忆的记忆会自动增强（access_count → retention_score）
- 记忆注入 prompt 时不是简单堆砌，而是按相关性和重要性精选
"""

from datetime import datetime, timezone
from logging import getLogger
from typing import Protocol

from app.memory.models import (
    MemoryCollection,
    MemoryEmotion,
    MemoryEntry,
    MemoryEvent,
    MemoryKind,
    MemoryStrength,
)
from app.memory.repository import MemoryRepository
from app.persona.models import PersonalityDimensions

logger = getLogger(__name__)


class MemoryService:
    """记忆系统统一门面

    所有关于记忆的操作都通过这个类进行，
    与 PersonaService 的关系：
    - PersonaService 提供人格配置，MemoryService 据此调整记忆行为
    - 对话产生的情绪通过 PersonaService → 影响 MemoryService 的存储策略
    """

    def __init__(
        self,
        repository: MemoryRepository | None = None,
        personality: PersonalityDimensions | None = None,
    ) -> None:
        self.repository = repository
        self.personality = personality or PersonalityDimensions()

    # ══════════════════════════════════════════════
    # 1. 基础 CRUD
    # ══════════════════════════════════════════════

    def save(self, entry: MemoryEntry) -> MemoryEntry:
        """保存一条新记忆"""
        if self.repository is not None:
            # 转换为存储层事件写入底层仓库
            event = MemoryEvent.from_entry(entry)
            self.repository.save_event(event)
        return entry

    def create(
        self,
        kind: MemoryKind,
        content: str,
        *,
        role: str | None = None,
        strength: MemoryStrength = MemoryStrength.NORMAL,
        importance: int = 5,
        emotion_tag: MemoryEmotion = MemoryEmotion.NEUTRAL,
        keywords: list[str] | None = None,
        subject: str | None = None,
        source_context: str | None = None,
    ) -> MemoryEntry:
        """创建并保存一条新记忆"""
        entry = MemoryEntry(
            kind=kind,
            content=content,
            role=role,
            strength=self._adjust_strength_for_personality(kind, strength),
            importance=importance,
            emotion_tag=emotion_tag,
            keywords=keywords or self._extract_keywords(content),
            subject=subject,
            source_context=source_context,
        )
        return self.save(entry)

    def delete(self, memory_id: str) -> bool:
        """删除指定 ID 的记忆

        Args:
            memory_id: MemoryEntry.id（如 mem_20260405...）

        Returns:
            是否删除成功
        """
        if self.repository is None:
            logger.warning("Cannot delete memory %s: no repository", memory_id)
            return False

        result = self.repository.delete_event(memory_id)
        if result:
            logger.info("Deleted memory %s", memory_id)
        else:
            logger.warning("Failed to delete memory %s: not found", memory_id)
        return result

    def delete_many(self, memory_ids: list[str]) -> dict[str, int]:
        """批量删除多条记忆

        Args:
            memory_ids: 要删除的记忆 ID 列表

        Returns:
            {"deleted": 成功删除数量, "failed": 失败数量}
        """
        if self.repository is None:
            logger.warning("Cannot delete memories: no repository")
            return {"deleted": 0, "failed": len(memory_ids)}

        deleted_count = 0
        failed_count = 0

        for memory_id in memory_ids:
            if self.repository.delete_event(memory_id):
                deleted_count += 1
            else:
                failed_count += 1

        logger.info("Batch delete: %d succeeded, %d failed", deleted_count, failed_count)
        return {"deleted": deleted_count, "failed": failed_count}

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        kind: MemoryKind | None = None,
        importance: int | None = None,
        strength: MemoryStrength | None = None,
        emotion_tag: MemoryEmotion | None = None,
        keywords: list[str] | None = None,
        subject: str | None = None,
    ) -> bool:
        """更新指定 ID 的记忆字段

        Returns:
            是否更新成功
        """
        if self.repository is None:
            logger.warning("Cannot update memory %s: no repository", memory_id)
            return False

        # 构建需要更新的字段（过滤掉 None）
        update_kwargs: dict[str, object] = {}
        if content is not None:
            update_kwargs["content"] = content
            # 如果内容变了，重新提取关键词
            if keywords is None:
                update_kwargs.setdefault("keywords", self._extract_keywords(content))
        if kind is not None:
            update_kwargs["kind"] = kind.value
        if importance is not None:
            update_kwargs["importance"] = importance
        if strength is not None:
            update_kwargs["strength"] = strength.value
        if emotion_tag is not None:
            update_kwargs["emotion_tag"] = emotion_tag.value
        if keywords is not None:
            update_kwargs["keywords"] = keywords
        if subject is not None:
            update_kwargs["subject"] = subject

        if not update_kwargs:
            return True  # 没有要更新的内容，算成功

        result = self.repository.update_event(memory_id, **update_kwargs)
        if result:
            logger.info("Updated memory %s with fields: %s", memory_id, list(update_kwargs.keys()))
        else:
            logger.warning("Failed to update memory %s: not found", memory_id)
        return result

    def star(self, memory_id: str, important: bool = True) -> bool:
        """标记/取消标记一条记忆为重要

        标记重要时将 importance 设为 9（core 级），
        取消标记时恢复为默认值 5。
        """
        new_importance = 9 if important else 5
        return self.update(memory_id, importance=new_importance)

    def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """根据 ID 获取单条记忆"""
        if self.repository is None:
            return None
        recent = self.list_recent(limit=500)
        for entry in recent.entries:
            if entry.id == memory_id:
                return entry
        return None

    def list_recent(
        self,
        limit: int = 20,
        kinds: list[MemoryKind] | None = None,
    ) -> MemoryCollection:
        """获取最近记忆"""
        if self.repository is None:
            return MemoryCollection(entries=[], total_count=0)

        events = self.repository.list_recent(limit * 3)  # 多取一些以便过滤
        entries = [e.to_entry() for e in events]

        # 按 kind 过滤
        if kinds:
            entries = [e for e in entries if e.kind in kinds]

        # 按时间倒序
        entries.sort(key=lambda e: e.created_at, reverse=True)

        return MemoryCollection(
            entries=entries[:limit],
            total_count=len(entries),
            query_summary=f"最近 {limit} 条记录",
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        kinds: list[MemoryKind] | None = None,
    ) -> MemoryCollection:
        """搜索相关记忆

        结合关键词匹配 + 人格偏好排序
        """
        if self.repository is None:
            return MemoryCollection(entries=[], total_count=0)

        events = self.repository.search_relevant(query, limit=limit * 3)
        entries = [e.to_entry() for e in events]

        # 按 kind 过滤
        if kinds:
            entries = [e for e in entries if e.kind in kinds]

        # 人格感知的重排序
        entries = self._rank_by_personality(entries, query)

        return MemoryCollection(
            entries=entries[:limit],
            total_count=len(entries),
            query_summary=f"搜索「{query[:20]}」的结果",
        )

    # ══════════════════════════════════════════════
    # 2. 对话驱动的记忆提取
    # ══════════════════════════════════════════════

    def extract_from_conversation(
        self,
        user_message: str,
        assistant_response: str,
    ) -> list[MemoryEntry]:
        """从对话中自动提取值得记住的信息

        策略：
        1. 用户主动分享的个人信息 → fact（高重要性）
        2. 用户表达偏好/喜好 → fact
        3. 达成约定/承诺 → fact（core 强度）
        4. 情绪强烈的对话片段 → episodic/emotional
        5. 其他对话 → chat_raw（低强度）
        """
        extracted: list[MemoryEntry] = []

        # ── 用户偏好检测 ──
        pref_patterns = [
            ("我喜欢", "用户表达了喜好", 7),
            ("我不喜欢", "用户表达了厌恶", 7),
            ("我讨厌", "用户表达了讨厌的事物", 7),
            ("我喜欢用", "用户的使用偏好", 6),
            ("习惯用", "用户的使用习惯", 6),
            ("我是", "用户的自我介绍", 8),
            ("我叫", "用户的姓名", 9),
            ("我的名字", "用户的姓名信息", 9),
            ("记得", "希望数字人记住的事", 8),
            ("别忘了", "重要提醒", 9),
            ("以后", "未来的约定或计划", 7),
            ("明天", "时间相关的约定", 6),
            ("下周", "时间相关的约定", 6),
            ("答应", "承诺事项", 9),
            ("保证", "承诺事项", 9),
            ("一定", "强调性承诺", 8),
        ]

        for pattern, description, importance in pref_patterns:
            if pattern in user_message:
                # 提取包含模式的完整句子
                sentence = self._extract_sentence(user_message, pattern)
                entry = self.create(
                    kind=MemoryKind.FACT,
                    content=sentence or f"{description}：{user_message[:60]}",
                    role="user",
                    strength=MemoryStrength.VIVID if importance >= 8 else MemoryStrength.NORMAL,
                    importance=importance,
                    emotion_tag=MemoryEmotion.POSITIVE if "喜欢" in pattern else MemoryEmotion.NEUTRAL,
                    subject="用户偏好",
                    source_context=f"用户说：{user_message[:40]}",
                )
                extracted.append(entry)
                break  # 每条消息最多提取一条 fact

        # ── 情绪强烈检测 ──
        emotional_keywords = {
            "positive": ["太棒了", "太好了", "开心", "高兴", "爱", "感谢", "谢谢"],
            "negative": ["生气", "烦", "讨厌", "难过", "伤心", "失望", "无语"],
        }
        msg_lower = user_message.lower()

        for emotion, keywords in emotional_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    entry = self.create(
                        kind=MemoryKind.EMOTIONAL,
                        content=f"用户在对话中表现出{emotion}情绪：「{user_message[:50]}」",
                        role="user",
                        strength=MemoryStrength.WEAK,
                        importance=4,
                        emotion_tag=MemoryEmotion(emotion) if emotion != "positive" else MemoryEmotion.POSITIVE,
                        source_context=f"情绪化对话",
                    )
                    extracted.append(entry)
                    break

        # ── 默认：原始对话记录 ──
        # 用户消息
        chat_user = self.create(
            kind=MemoryKind.CHAT_RAW,
            content=user_message,
            role="user",
            strength=MemoryStrength.FAINT,
            importance=2,
        )
        extracted.append(chat_user)

        # AI 回复
        chat_asst = self.create(
            kind=MemoryKind.CHAT_RAW,
            content=assistant_response,
            role="assistant",
            strength=MemoryStrength.FAINT,
            importance=2,
        )
        extracted.append(chat_asst)

        logger.info("Extracted %d memory entries from conversation", len(extracted))
        return extracted

    # ══════════════════════════════════════════════
    # 3. 记忆生命周期
    # ══════════════════════════════════════════════

    def strengthen(self, memory_id: str) -> bool:
        """强化一条记忆（被回忆时调用）"""
        # 由于底层是 append-only 文件，这里只做概念性的标记
        # 实际的 access_count 在内存中的 entry 上更新
        logger.debug("Strengthening memory %s", memory_id)
        return True

    def weaken_old_memories(self, days_threshold: int = 30) -> int:
        """淡化旧记忆（返回受影响的数量）

        注意：由于底层存储是 append-only JSONL，
        这里返回的是"如果可以修改会影响的数量"。
        未来升级为数据库时可真正执行。
        """
        if self.repository is None:
            return 0

        cutoff = datetime.now(timezone.utc).timestamp() - (days_threshold * 86400)
        events = self.repository.list_recent(limit=1000)
        old_count = sum(1 for e in events if e.created_at.timestamp() < cutoff)

        if old_count > 0:
            logger.info("Found %d memories older than %d days (conceptual decay)", old_count, days_threshold)

        return old_count

    # ══════════════════════════════════════════════
    # 4. Prompt 集成
    # ══════════════════════════════════════════════

    def build_memory_prompt_context(
        self,
        user_message: str | None = None,
        max_chars: int = 800,
    ) -> str:
        """构建用于注入 system prompt 的记忆上下文

        策略：
        1. 如果有用户消息，先搜索相关记忆
        2. 加入最近的高强度事实记忆
        3. 加入最近的情绪印记（影响回复语气）
        4. 总字符数控制
        """
        parts: list[str] = []

        if user_message and self.repository:
            # 搜索相关记忆
            relevant = self.search(user_message, limit=5)
            if relevant.entries:
                context = relevant.to_prompt_context(max_chars=max_chars // 2)
                if context:
                    parts.append(context)

        # 最近的重要事实和情景记忆
        recent = self.list_recent(limit=20)
        important_entries = [
            e for e in recent.entries
            if e.kind in (MemoryKind.FACT, MemoryKind.EPISODIC)
            and e.importance >= 6
        ][:5]

        if important_entries:
            fact_collection = MemoryCollection(entries=important_entries)
            facts_context = fact_collection.to_prompt_context(max_chars=max_chars // 2)
            if facts_context:
                parts.append(facts_context)

        if not parts:
            return ""

        header = "【你记得的事情】\n"
        return header + "\n".join(parts)

    def get_memory_summary(self) -> dict:
        """获取记忆系统的统计摘要"""
        if self.repository is None:
            return {
                "total_estimated": 0,
                "by_kind": {},
                "recent_count": 0,
                "strong_memories": 0,
                "available": False,
            }

        recent = self.list_recent(limit=200)
        by_kind: dict[str, int] = {}
        strong = 0

        for entry in recent.entries:
            k = entry.kind.value
            by_kind[k] = by_kind.get(k, 0) + 1
            if entry.strength in (MemoryStrength.VIVID, MemoryStrength.CORE):
                strong += 1

        return {
            "total_estimated": recent.total_count,
            "by_kind": by_kind,
            "recent_count": len(recent.entries),
            "strong_memories": strong,
            "available": True,
        }

    def get_memory_timeline(self, limit: int = 30) -> list[dict]:
        """获取记忆时间线（前端展示用）"""
        recent = self.list_recent(limit=limit)
        return [entry.to_display_dict() for entry in recent.entries]

    # ══════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════

    def _adjust_strength_for_personality(
        self,
        kind: MemoryKind,
        base_strength: MemoryStrength,
    ) -> MemoryStrength:
        """根据性格调整初始记忆强度

        - 高开放性 → 新奇事实更强
        - 高宜人情性 → 关于人的记忆更强
        - 高神经质 → 情绪印记更强
        """
        p = self.personality

        match kind:
            case MemoryKind.FACT:
                if p.openness >= 70:
                    return self._boost_strength(base_strength)
            case MemoryKind.EPISODIC:
                if p.agreeableness >= 70:
                    return self._boost_strength(base_strength)
            case MemoryKind.EMOTIONAL:
                if p.neuroticism >= 60:
                    return self._boost_strength(base_strength)
                elif p.neuroticism <= 30:
                    return self._weaken_strength(base_strength)

        return base_strength

    def _rank_by_personality(
        self,
        entries: list[MemoryEntry],
        query: str,
    ) -> list[MemoryEntry]:
        """根据性格对搜索结果重排序"""
        p = self.personality

        def score(entry: MemoryEntry) -> float:
            base = entry.retention_score

            # 高开放性：偏好事实和知识
            if p.openness >= 70 and entry.kind in (MemoryKind.FACT, MemoryKind.SEMANTIC):
                base += 0.1

            # 高外向性：偏好情景记忆
            if p.extraversion >= 70 and entry.kind == MemoryKind.EPISODIC:
                base += 0.1

            # 高神经质：不容易忘记负面情绪记忆
            if p.neuroticism >= 60 and entry.emotion_tag == MemoryEmotion.NEGATIVE:
                base += 0.15

            # 高宜人性：偏好正面记忆
            if p.agreeableness >= 70 and entry.emotion_tag == MemoryEmotion.POSITIVE:
                base += 0.08

            return base

        return sorted(entries, key=score, reverse=True)

    def _extract_keywords(self, text: str) -> list[str]:
        """简单的中文关键词提取"""
        import re
        # 中文词汇（2-4 字）
        cjk_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        # 英文单词
        en_words = re.findall(r'[A-Za-z]{3,}', text.lower())
        return list(set(cjk_words[:10] + en_words[:5]))

    def _extract_sentence(self, text: str, anchor: str) -> str | None:
        """从文本中提取包含锚点的句子"""
        idx = text.find(anchor)
        if idx < 0:
            return None

        # 向前找句首
        start = idx
        while start > 0 and text[start - 1] not in '。！？\n':
            start -= 1

        # 向后找句尾
        end = idx + len(anchor)
        while end < len(text) and text[end] not in '。！？\n':
            end += 1

        sentence = text[start:end].strip()
        return sentence if len(sentence) > 3 else None

    @staticmethod
    def _boost_strength(strength: MemoryStrength) -> MemoryStrength:
        """提升一级"""
        order = [
            MemoryStrength.FAINT,
            MemoryStrength.WEAK,
            MemoryStrength.NORMAL,
            MemoryStrength.VIVID,
            MemoryStrength.CORE,
        ]
        try:
            idx = order.index(strength)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return strength

    @staticmethod
    def _weaken_strength(strength: MemoryStrength) -> MemoryStrength:
        """降低一级"""
        order = [
            MemoryStrength.FAINT,
            MemoryStrength.WEAK,
            MemoryStrength.NORMAL,
            MemoryStrength.VIVID,
            MemoryStrength.CORE,
        ]
        try:
            idx = order.index(strength)
            if idx > 0:
                return order[idx - 1]
        except ValueError:
            pass
        return strength
