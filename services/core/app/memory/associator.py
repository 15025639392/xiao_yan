"""记忆关联器

实现记忆之间的智能关联，基于语义相似度、时间邻近性、情绪等因素
"""

import re
from datetime import datetime, timezone, timedelta
from typing import List

from app.memory.models import MemoryEvent, MemoryKind, MemoryEmotion
from app.memory.repository import MemoryRepository


class MemoryAssociator:
    """记忆关联器

    功能：
    - 为新记忆事件建立关联
    - 查找相关记忆
    - 计算记忆相似度
    """

    def __init__(self, repository: MemoryRepository):
        """初始化记忆关联器

        Args:
            repository: 记忆存储库
        """
        self.repository = repository

    def associate_events(
        self,
        new_events: List[MemoryEvent]
    ) -> None:
        """为新记忆事件建立关联

        Args:
            new_events: 新的记忆事件列表
        """
        # 获取所有现有记忆
        all_events = self.repository.list_recent(limit=1000)

        for new_event in new_events:
            # 先保存新记忆
            self.repository.save_event(new_event)

            # 查找相关记忆
            related_events = self._find_related_events(
                new_event,
                all_events
            )

            # 在新记忆中记录关联
            related_ids = [e.entry_id for e in related_events]
            # 更新repository中的事件
            self.repository.update_event(
                new_event.entry_id,
                related_memory_ids=related_ids
            )

            # 更新现有记忆的关联（通过重新保存）
            for related_event in related_events:
                # 获取相关事件的当前related_memory_ids
                current_related = related_event.related_memory_ids if related_event.related_memory_ids else []
                if new_event.entry_id not in current_related:
                    current_related.append(new_event.entry_id)
                    # 重新保存以更新关联
                    self.repository.update_event(
                        related_event.entry_id,
                        related_memory_ids=current_related
                    )

    def _find_related_events(
        self,
        target_event: MemoryEvent,
        existing_events: List[MemoryEvent]
    ) -> List[MemoryEvent]:
        """查找相关记忆

        Args:
            target_event: 目标记忆事件
            existing_events: 现有记忆事件列表

        Returns:
            相关记忆事件列表（按相似度排序）
        """
        related = []

        for event in existing_events:
            # 跳过自己
            if event.entry_id == target_event.entry_id:
                continue

            similarity_score = self._calculate_similarity(
                target_event,
                event
            )

            # 相似度阈值
            if similarity_score > 0.5:
                related.append({
                    'event': event,
                    'score': similarity_score
                })

        # 按相似度排序，返回前5个
        related.sort(key=lambda x: x['score'], reverse=True)
        return [item['event'] for item in related[:5]]

    def _calculate_similarity(
        self,
        event1: MemoryEvent,
        event2: MemoryEvent
    ) -> float:
        """计算记忆相似度

        考虑因素：
        1. 内容相似度（关键词重叠）：40%
        2. 记忆类型相似度：20%
        3. 时间邻近性：20%
        4. 情绪相似度：20%

        Args:
            event1: 记忆事件1
            event2: 记忆事件2

        Returns:
            相似度分数（0.0-1.0）
        """
        score = 0.0

        # 1. 内容相似度（关键词重叠）
        content_similarity = self._content_similarity(
            event1.content,
            event2.content
        )
        score += content_similarity * 0.4

        # 2. 记忆类型相似度
        if event1.kind == event2.kind:
            score += 0.2

        # 3. 时间邻近性
        time_diff = abs(
            (event1.created_at - event2.created_at).total_seconds()
        )
        if time_diff < 3600:  # 1小时内
            score += 0.2
        elif time_diff < 86400:  # 1天内
            score += 0.1
        elif time_diff < 604800:  # 1周内
            score += 0.05

        # 4. 情绪相似度
        # MemoryEvent没有emotion_tag字段，这里简化处理
        # 如果需要，可以通过to_entry()获取
        entry1 = event1.to_entry()
        entry2 = event2.to_entry()
        if entry1.emotion_tag == entry2.emotion_tag:
            score += 0.2

        return min(score, 1.0)  # 确保不超过1.0

    def _content_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似度

        使用关键词重叠率（Jaccard相似度）

        Args:
            content1: 内容1
            content2: 内容2

        Returns:
            相似度分数（0.0-1.0）
        """
        # 分词
        words1 = self._tokenize(content1)
        words2 = self._tokenize(content2)

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _tokenize(self, text: str) -> set:
        """文本分词

        处理中文和英文

        Args:
            text: 待分词文本

        Returns:
            词集合
        """
        tokens = set()

        # 中文词汇（2-4字）
        cjk_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        tokens.update(cjk_words)

        # 英文单词
        en_words = re.findall(r'[A-Za-z]{3,}', text.lower())
        tokens.update(en_words)

        # 单个汉字
        cjk_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.update(cjk_chars)

        return tokens

    def find_related_memories(
        self,
        memory_id: str,
        limit: int = 5
    ) -> List[MemoryEvent]:
        """查找与指定记忆相关的其他记忆

        Args:
            memory_id: 记忆ID
            limit: 返回数量限制

        Returns:
            相关记忆列表
        """
        # 获取目标记忆
        all_events = self.repository.list_recent(limit=1000)
        target_event = None
        for event in all_events:
            if event.entry_id == memory_id:
                target_event = event
                break

        if target_event is None:
            return []

        # 查找相关记忆
        related_events = self._find_related_events(
            target_event,
            all_events
        )

        return related_events[:limit]
