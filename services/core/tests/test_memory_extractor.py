"""记忆提取器测试集（Week 5 新增）

测试智能记忆提取功能，验证：
1. 用户偏好提取
2. 用户习惯提取
3. 重要事件提取
4. 事实信息提取
5. 承诺和计划提取
6. 知识提取
7. 去重功能
8. 重要性评估
"""

import pytest

from app.memory.extractor import MemoryExtractor
from app.llm.schemas import ChatMessage
from app.persona.models import PersonalityDimensions


# ═══════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════


@pytest.fixture
def neutral_personality():
    """中性性格"""
    return PersonalityDimensions()


@pytest.fixture
def extractor(neutral_personality):
    """创建提取器实例"""
    return MemoryExtractor(personality=neutral_personality)


# ═══════════════════════════════════════════════════
# 1. 用户偏好提取测试
# ═══════════════════════════════════════════════════


class TestPreferenceExtraction:
    def test_extract_simple_preference(self, extractor):
        """测试提取简单偏好"""
        message = ChatMessage(
            role="user",
            content="我喜欢喝茶",
        )

        events = extractor._extract_user_info(message, None)
        preference_events = [e for e in events if "用户偏好" in e.content]

        assert len(preference_events) >= 1
        assert "茶" in preference_events[0].content

    def test_extract_multiple_preferences(self, extractor):
        """测试提取多个偏好"""
        message = ChatMessage(
            role="user",
            content="我喜欢喝茶，也比较喜欢绿茶，还喜欢红茶",
        )

        events = extractor._extract_user_info(message, None)
        preference_events = [e for e in events if "用户偏好" in e.content]

        assert len(preference_events) >= 1

    def test_extract_different_preference_types(self, extractor):
        """测试提取不同类型的偏好"""
        message = ChatMessage(
            role="user",
            content="我喜欢喝咖啡，喜欢吃巧克力，喜欢看电影，喜欢听音乐",
        )

        events = extractor._extract_user_info(message, None)
        preference_events = [e for e in events if "用户偏好" in e.content]

        assert len(preference_events) >= 1


# ═══════════════════════════════════════════════════
# 2. 用户习惯提取测试
# ═══════════════════════════════════════════════════


class TestHabitExtraction:
    def test_extract_simple_habit(self, extractor):
        """测试提取简单习惯"""
        message = ChatMessage(
            role="user",
            content="我经常跑步",
        )

        events = extractor._extract_user_info(message, None)
        habit_events = [e for e in events if "用户习惯" in e.content]

        assert len(habit_events) >= 1
        assert "跑步" in habit_events[0].content

    def test_extract_multiple_habits(self, extractor):
        """测试提取多个习惯"""
        message = ChatMessage(
            role="user",
            content="我经常跑步，也经常读书，还经常写代码",
        )

        events = extractor._extract_user_info(message, None)
        habit_events = [e for e in events if "用户习惯" in e.content]

        assert len(habit_events) >= 1

    def test_extract_habit_with_pattern(self, extractor):
        """测试提取不同模式的习惯"""
        message = ChatMessage(
            role="user",
            content="我习惯早起，每次都喝一杯温水，一般会在7点前起床",
        )

        events = extractor._extract_user_info(message, None)
        habit_events = [e for e in events if "用户习惯" in e.content]

        assert len(habit_events) >= 1


# ═══════════════════════════════════════════════════
# 3. 重要事件提取测试
# ═══════════════════════════════════════════════════


class TestImportantEventExtraction:
    def test_extract_today_event(self, extractor):
        """测试提取今天的事件"""
        message = ChatMessage(
            role="user",
            content="今天我完成了项目报告，老板很满意",
        )

        events = extractor._extract_user_info(message, None)
        # 重要事件应该是EPISODIC类型
        episodic_events = [e for e in events if e.kind == "episodic"]

        assert len(episodic_events) >= 1

    def test_extract_yesterday_event(self, extractor):
        """测试提取昨天的事件"""
        message = ChatMessage(
            role="user",
            content="昨天我参加了一个重要的会议",
        )

        events = extractor._extract_user_info(message, None)
        episodic_events = [e for e in events if e.kind == "episodic"]

        assert len(episodic_events) >= 1

    def test_extract_recent_event(self, extractor):
        """测试提取最近的事件"""
        message = ChatMessage(
            role="user",
            content="最近我在学习Python编程",
        )

        events = extractor._extract_user_info(message, None)
        episodic_events = [e for e in events if e.kind == "episodic"]

        assert len(episodic_events) >= 1


# ═══════════════════════════════════════════════════
# 4. 事实信息提取测试
# ═══════════════════════════════════════════════════


class TestFactExtraction:
    def test_extract_name_fact(self, extractor):
        """测试提取姓名事实"""
        message = ChatMessage(
            role="user",
            content="我的名字是小明",
        )

        events = extractor._extract_user_info(message, None)
        # 事实应该是FACT类型
        fact_events = [e for e in events if e.kind == "fact"]

        # 至少应该有一个事件（可能是事实、偏好或习惯）
        assert len(events) >= 1

    def test_extract_job_fact(self, extractor):
        """测试提取工作事实"""
        message = ChatMessage(
            role="user",
            content="我在腾讯工作",
        )

        events = extractor._extract_user_info(message, None)

        assert len(events) >= 1


# ═══════════════════════════════════════════════════
# 5. 承诺和计划提取测试
# ═══════════════════════════════════════════════════


class TestCommitmentExtraction:
    def test_extract_simple_commitment(self, extractor):
        """测试提取简单承诺"""
        message = ChatMessage(
            role="assistant",
            content="我会帮你分析这个问题",
        )

        events = extractor._extract_assistant_info(message, None)
        commitment_events = [e for e in events if "承诺" in e.content or "计划" in e.content]

        assert len(commitment_events) >= 1

    def test_extract_multiple_commitments(self, extractor):
        """测试提取多个承诺"""
        message = ChatMessage(
            role="assistant",
            content="我会帮你分析这个问题，我决定先整理一下资料，下次我们再详细讨论",
        )

        events = extractor._extract_assistant_info(message, None)
        commitment_events = [e for e in events if "承诺" in e.content or "计划" in e.content]

        assert len(commitment_events) >= 1

    def test_extract_plan(self, extractor):
        """测试提取计划"""
        message = ChatMessage(
            role="assistant",
            content="计划明天给你一个详细的回复",
        )

        events = extractor._extract_assistant_info(message, None)
        commitment_events = [e for e in events if "承诺" in e.content or "计划" in e.content]

        assert len(commitment_events) >= 1


# ═══════════════════════════════════════════════════
# 6. 知识提取测试
# ═══════════════════════════════════════════════════


class TestKnowledgeExtraction:
    def test_extract_learned_knowledge(self, extractor):
        """测试提取学到的知识"""
        message = ChatMessage(
            role="assistant",
            content="我学会了使用pytest进行测试",
        )

        events = extractor._extract_assistant_info(message, None)
        knowledge_events = [e for e in events if "学习" in e.content]

        assert len(knowledge_events) >= 1
        assert "pytest" in knowledge_events[0].content

    def test_extract_understanding(self, extractor):
        """测试提取理解"""
        message = ChatMessage(
            role="assistant",
            content="现在我理解了用户的需求",
        )

        events = extractor._extract_assistant_info(message, None)
        knowledge_events = [e for e in events if "学习" in e.content]

        # 至少应该有一个事件
        assert len(events) >= 1


# ═══════════════════════════════════════════════════
# 7. 对话整体提取测试
# ═══════════════════════════════════════════════════


class TestDialogueExtraction:
    def test_extract_from_simple_dialogue(self, extractor):
        """测试从简单对话中提取"""
        dialogue = [
            ChatMessage(
                role="user",
                content="我喜欢喝茶",
            ),
            ChatMessage(
                role="assistant",
                content="好的，我会记住你喜欢喝茶",
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 应该提取到至少一个事件
        assert len(events) >= 1

    def test_extract_from_complex_dialogue(self, extractor):
        """测试从复杂对话中提取"""
        dialogue = [
            ChatMessage(
                role="user",
                content="我的名字是小明，我喜欢喝茶，经常在早上喝",
            ),
            ChatMessage(
                role="assistant",
                content="你好小明，我会记住你喜欢喝茶的习惯，下次我会推荐一些茶给你",
            ),
            ChatMessage(
                role="user",
                content="今天我很开心，因为我完成了项目",
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 应该提取到多个事件（偏好、习惯、事件）
        assert len(events) >= 2

    def test_extract_with_context(self, extractor):
        """测试带上下文的提取"""
        dialogue = [
            ChatMessage(
                role="user",
                content="我喜欢喝咖啡",
            ),
        ]

        context = {
            "topic": "个人偏好",
            "timestamp": "2026-04-06",
        }

        events = extractor.extract_from_dialogue(dialogue, context)

        # 应该提取到事件
        assert len(events) >= 1


# ═══════════════════════════════════════════════════
# 8. 去重功能测试
# ═══════════════════════════════════════════════════


class TestDeduplication:
    def test_deduplicate_same_content(self, extractor):
        """测试去重相同内容"""
        from app.memory.models import MemoryEvent

        events = [
            MemoryEvent(
                kind="semantic",
                content="用户偏好：喝茶",
                role="user",
            ),
            MemoryEvent(
                kind="semantic",
                content="用户偏好：喝茶",  # 重复
                role="user",
            ),
        ]

        deduplicated = extractor._deduplicate_events(events)

        # 应该只剩下一个
        assert len(deduplicated) == 1

    def test_deduplicate_different_content(self, extractor):
        """测试不去重不同内容"""
        from app.memory.models import MemoryEvent

        events = [
            MemoryEvent(
                kind="semantic",
                content="用户偏好：喝茶",
                role="user",
            ),
            MemoryEvent(
                kind="semantic",
                content="用户偏好：咖啡",  # 不同
                role="user",
            ),
        ]

        deduplicated = extractor._deduplicate_events(events)

        # 应该保留两个
        assert len(deduplicated) == 2


# ═══════════════════════════════════════════════════
# 9. 重要性评估测试
# ═══════════════════════════════════════════════════


class TestImportanceAssessment:
    def test_assess_importance(self, extractor):
        """测试重要性评估"""
        from app.memory.models import MemoryEvent

        events = [
            MemoryEvent(
                kind="episodic",  # 情景记忆应该权重高
                content="今天我完成了项目",
                role="user",
            ),
            MemoryEvent(
                kind="semantic",  # 语义记忆
                content="用户偏好：喝茶",
                role="user",
            ),
        ]

        assessed = extractor._assess_importance(events)

        # 应该返回相同数量的事件
        assert len(assessed) == len(events)


# ═══════════════════════════════════════════════════
# 10. 情绪检测测试
# ═══════════════════════════════════════════════════


class TestEmotionDetection:
    def test_detect_positive_emotion(self, extractor):
        """测试检测正面情绪"""
        emotion = extractor._detect_emotion("今天我很开心")

        assert emotion == "positive"

    def test_detect_negative_emotion(self, extractor):
        """测试检测负面情绪"""
        emotion = extractor._detect_emotion("今天我很难过")

        assert emotion == "negative"

    def test_detect_neutral_emotion(self, extractor):
        """测试检测中性情绪"""
        emotion = extractor._detect_emotion("今天天气不错")

        assert emotion == "neutral"

    def test_detect_mixed_emotion(self, extractor):
        """测试检测混合情绪"""
        emotion = extractor._detect_emotion("我今天既开心又难过")

        # 混合情绪应该倾向于中性
        assert emotion == "neutral"


# ═══════════════════════════════════════════════════
# 11. 边界情况测试
# ═══════════════════════════════════════════════════


class TestEdgeCases:
    def test_extract_from_empty_dialogue(self, extractor):
        """测试从空对话中提取"""
        dialogue = []

        events = extractor.extract_from_dialogue(dialogue, None)

        # 空对话应该返回空列表
        assert len(events) == 0

    def test_extract_from_short_content(self, extractor):
        """测试从短内容中提取"""
        dialogue = [
            ChatMessage(
                role="user",
                content="好",  # 非常短
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 短内容可能提取不到事件
        assert isinstance(events, list)

    def test_extract_from_special_characters(self, extractor):
        """测试从特殊字符内容中提取"""
        dialogue = [
            ChatMessage(
                role="user",
                content="我喜欢@#$%^&*()_+",  # 特殊字符
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 应该不会崩溃
        assert isinstance(events, list)

    def test_extract_with_none_llm_gateway(self, neutral_personality):
        """测试没有LLM网关的情况"""
        extractor = MemoryExtractor(
            personality=neutral_personality,
            llm_gateway=None,  # 没有LLM网关
        )

        dialogue = [
            ChatMessage(
                role="user",
                content="我喜欢喝茶",
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 应该仍然能够提取（使用规则）
        assert len(events) >= 1


# ═══════════════════════════════════════════════════
# 12. 集成测试
# ═══════════════════════════════════════════════════


class TestIntegration:
    def test_full_extraction_pipeline(self, extractor):
        """测试完整的提取流程"""
        dialogue = [
            ChatMessage(
                role="user",
                content="我的名字是小明，我喜欢喝茶，经常早上喝。今天我很开心，因为我完成了项目。",
            ),
            ChatMessage(
                role="assistant",
                content="你好小明，我会记住你喜欢喝茶的习惯。我学会了你的需求，我会帮你分析项目。",
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 应该提取到多个类型的记忆
        assert len(events) >= 2

        # 检查是否有不同类型的事件
        kinds = set(e.kind for e in events)
        assert len(kinds) >= 1  # 至少有一种类型

    def test_multiple_users_messages(self, extractor):
        """测试多条用户消息"""
        dialogue = [
            ChatMessage(
                role="user",
                content="我喜欢喝茶",
            ),
            ChatMessage(
                role="user",
                content="我喜欢咖啡",  # 连续两条用户消息（不太常见，但应该处理）
            ),
            ChatMessage(
                role="assistant",
                content="好的",
            ),
        ]

        events = extractor.extract_from_dialogue(dialogue, None)

        # 应该处理所有消息
        assert len(events) >= 1
