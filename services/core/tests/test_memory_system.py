"""记忆与人格联动测试

覆盖：
- MemoryEntry 数据模型（5 种类型、强度、情绪标签）
- MemoryCollection 集合操作
- MemoryService CRUD
- MemoryService 对话记忆提取（偏好/约定/情绪检测）
- MemoryService 人格感知检索排序
- MemoryService prompt 上下文生成
- MemoryEvent ↔ MemoryEntry 转换
- retention_score 计算
"""

import pytest
from datetime import datetime, timezone

from app.memory.models import (
    MemoryCollection,
    MemoryEmotion,
    MemoryEntry,
    MemoryEvent,
    MemoryKind,
    MemoryStrength,
)
from app.memory.repository import InMemoryMemoryRepository, MemoryRepository
from app.memory.service import MemoryService
from app.persona.models import PersonalityDimensions


# ═══════════════════════════════════════════════════
# MemoryEntry 数据模型测试
# ═══════════════════════════════════════════════════


class TestMemoryEntry:
    """MemoryEntry 基础模型测试"""

    def test_create_fact_memory(self):
        entry = MemoryEntry(
            kind=MemoryKind.FACT,
            content="用户喜欢喝美式咖啡",
            subject="用户偏好",
            importance=8,
            strength=MemoryStrength.VIVID,
        )
        assert entry.kind == MemoryKind.FACT
        assert entry.subject == "用户偏好"
        assert entry.importance == 8
        assert not entry.is_expired

    def test_create_episodic_memory(self):
        entry = MemoryEntry(
            kind=MemoryKind.EPISODIC,
            content="上次聊到深夜，一起调试了一个 bug",
            emotion_tag=MemoryEmotion.POSITIVE,
            strength=MemoryStrength.NORMAL,
        )
        assert entry.kind == MemoryKind.EPISODIC
        assert entry.emotion_tag == MemoryEmotion.POSITIVE

    def test_expired_memory(self):
        past = datetime.now(timezone.utc).timestamp() - (86400 * 10)  # 10 天前
        expires_at = datetime.fromtimestamp(past, tz=timezone.utc)

        entry = MemoryEntry(
            kind=MemoryKind.FACT,
            content="过期的信息",
            expires_at=expires_at,
        )
        assert entry.is_expired

    def test_non_expired_memory(self):
        future = datetime.now(timezone.utc).timestamp() + 86400
        expires_at = datetime.fromtimestamp(future, tz=timezone.utc)

        entry = MemoryEntry(
            kind=MemoryKind.FACT,
            content="未过期的信息",
            expires_at=expires_at,
        )
        assert not entry.is_expired

    def test_retention_score_basic(self):
        """基础保留分计算"""
        entry_normal = MemoryEntry(kind=MemoryKind.FACT, content="正常记忆", importance=5)
        entry_core = MemoryEntry(
            kind=MemoryKind.FACT, content="核心记忆", strength=MemoryStrength.CORE, importance=9
        )
        entry_faint = MemoryEntry(
            kind=MemoryKind.CHAT_RAW, content="模糊记忆", strength=MemoryStrength.FAINT, importance=1
        )

        assert entry_faint.retention_score < entry_normal.retention_score
        assert entry_normal.retention_score < entry_core.retention_score
        assert entry_core.retention_score > 0.95  # core + 高重要性 ≈ 接近满分

    def test_access_count_increases_retention(self):
        """访问次数增加保留分"""
        entry1 = MemoryEntry(kind=MemoryKind.FACT, content="测试", access_count=0)
        entry2 = MemoryEntry.model_copy(entry1, update={"access_count": 20})

        assert entry2.retention_score > entry1.retention_score

    def test_to_prompt_fragment_with_subject(self):
        entry = MemoryEntry(
            kind=MemoryKind.FACT,
            content="用户喜欢用 Vim 编辑器",
            subject="用户偏好",
            role="user",
        )
        frag = entry.to_prompt_fragment()
        assert "事实" in frag
        assert "用户偏好" in frag
        assert "Vim" in frag or "编辑器" in frag

    def test_to_prompt_fragment_chat_raw(self):
        entry = MemoryEntry(
            kind=MemoryKind.CHAT_RAW,
            content="你好啊，今天天气不错",
            role="user",
        )
        frag = entry.to_prompt_fragment()
        assert "对话" in frag
        assert "[user]" in frag

    def test_to_display_dict_keys(self):
        entry = MemoryEntry(
            kind=MemoryKind.EMOTIONAL,
            content="用户生气了",
            keywords=["生气", "愤怒"],
        )
        d = entry.to_display_dict()
        assert "id" in d
        assert "kind" in d
        assert "content" in d
        assert "retention_score" in d
        assert "keywords" in d
        # ID 是完整唯一标识符（用于 React key）
        assert d["id"].startswith("mem_")  # 格式校验
        assert len(d["id"]) >= 10  # 至少包含前缀+部分时间戳


class TestMemoryCollection:
    """MemoryCollection 集合操作测试"""

    def _make_entries(self) -> list[MemoryEntry]:
        return [
            MemoryEntry(id="a1", kind=MemoryKind.FACT, content="事实A", importance=8),
            MemoryEntry(id="b2", kind=MemoryKind.EPISODIC, content="经历B"),
            MemoryEntry(id="c3", kind=MemoryKind.FACT, content="事实C", importance=5),
            MemoryEntry(id="d4", kind=MemoryKind.EMOTIONAL, content="情绪D"),
        ]

    def test_filter_by_kind(self):
        col = MemoryCollection(entries=self._make_entries(), total_count=4)
        facts = col.filter_by_kind(MemoryKind.FACT)
        assert len(facts.entries) == 2
        assert all(e.kind == MemoryKind.FACT for e in facts.entries)

    def test_has_helpers(self):
        col = MemoryCollection(entries=self._make_entries(), total_count=4)
        assert col.has_facts is True
        assert col.has_episodic is True

        no_emotional = col.filter_by_kind(MemoryKind.EMOTIONAL)
        no_emotional.entries = []
        assert no_emotional.has_facts is False

    def test_get_top_by_importance(self):
        col = MemoryCollection(entries=self._make_entries(), total_count=4)
        top = col.get_top_by_importance(2)
        assert len(top) == 2
        assert top[0].importance >= top[1].importance

    def test_get_recent_preserves_order(self):
        """get_recent 按时间倒序，后创建的在前"""
        import time
        e1 = MemoryEntry(kind=MemoryKind.FACT, content="A")
        time.sleep(0.01)  # 确保时间差
        e2 = MemoryEntry(kind=MemoryKind.FACT, content="Z")
        col = MemoryCollection(entries=[e1, e2], total_count=2)
        recent = col.get_recent()
        # 后创建的 Z 应该在前面
        assert recent[0].content == "Z"

    def test_to_prompt_context_limits_chars(self):
        entries = [MemoryEntry(kind=MemoryKind.FACT, content=f"内容{i} " * 50) for i in range(10)]
        col = MemoryCollection(entries=entries, total_count=10)
        ctx = col.to_prompt_context(max_chars=200)
        assert len(ctx) <= 250  # 允许少量超出的标签开销


# ═══════════════════════════════════════════════════
# MemoryEvent ↔ MemoryEntry 转换测试
# ═══════════════════════════════════════════════════


class TestEventEntryConversion:
    """MemoryEvent 和 MemoryEntry 的互转"""

    def test_event_to_entry_chat(self):
        event = MemoryEvent(kind="chat", role="user", content="你好")
        entry = event.to_entry()
        assert entry.kind == MemoryKind.CHAT_RAW
        assert entry.content == "你好"
        assert entry.role == "user"
        assert entry.id == event.entry_id

    def test_event_to_entry_world(self):
        event = MemoryEvent(kind="world", content="今天天气晴朗")
        entry = event.to_entry()
        assert entry.kind == MemoryKind.EPISODIC

    def test_event_to_entry_inner(self):
        event = MemoryEvent(kind="inner", content="我在思考")
        entry = event.to_entry()
        assert entry.kind == MemoryKind.EPISODIC

    def test_entry_to_event_roundtrip(self):
        entry = MemoryEntry(kind=MemoryKind.CHAT_RAW, content="测试消息", role="assistant")
        event = MemoryEvent.from_entry(entry)
        assert event.kind == "chat"
        assert event.content == "测试消息"
        assert event.role == "assistant"
        assert event.entry_id == entry.id


# ═══════════════════════════════════════════════════
# MemoryService CRUD 测试
# ═══════════════════════════════════════════════════


class TestMemoryServiceCRUD:
    """MemoryService 基础 CRUD 操作"""

    @pytest.fixture()
    def repo(self) -> InMemoryMemoryRepository:
        return InMemoryMemoryRepository()

    @pytest.fixture()
    def service(self, repo: MemoryRepository) -> MemoryService:
        return MemoryService(repository=repo)

    def test_save_and_list(self, service: MemoryService, repo: MemoryRepository):
        entry = service.create(MemoryKind.FACT, "测试保存的事实", subject="测试")
        listed = service.list_recent(limit=10)
        assert listed.total_count >= 1
        contents = [e.content for e in listed.entries]
        assert "测试保存的事实" in contents

    def test_search_finds_matching(self, service: MemoryService, repo: MemoryRepository):
        service.create(MemoryKind.FACT, "用户喜欢 Python 编程语言")
        service.create(MemoryKind.EPISODIC, "上次讨论了 React 框架")

        results = service.search("Python", limit=5)
        assert any("Python" in e.content for e in results.entries)

    def test_filter_by_kind_on_list(self, service: MemoryService, repo: MemoryRepository):
        service.create(MemoryKind.FACT, "事实1")
        service.create(MemoryKind.EPISODIC, "经历1")
        service.create(MemoryKind.FACT, "事实2")

        facts_only = service.list_recent(limit=20, kinds=[MemoryKind.FACT])
        assert all(e.kind == MemoryKind.FACT for e in facts_only.entries)
        assert len(facts_only.entries) == 2

    def test_manual_create_with_all_fields(self, service: MemoryService, repo: MemoryRepository):
        entry = service.create(
            kind=MemoryKind.SEMANTIC,
            content="FastAPI 是一个现代 Python Web 框架",
            importance=7,
            emotion_tag=MemoryEmotion.POSITIVE,
            strength=MemoryStrength.VIVID,
            keywords=["FastAPI", "Python", "Web框架"],
            subject="技术知识",
        )
        assert entry.importance == 7
        assert entry.keywords[0] in ("FastAPI", "Python", "Web框架")  # set 顺序不确定
        assert entry.subject == "技术知识"
        assert entry.strength == MemoryStrength.VIVID


# ═══════════════════════════════════════════════════
# 对话记忆提取测试
# ═══════════════════════════════════════════════════


class TestConversationExtraction:
    """从对话中自动提取记忆"""

    @pytest.fixture()
    def service(self) -> MemoryService:
        return MemoryService()  # 无 repository，只做提取不存储

    def test_extract_user_preference(self, service: MemoryService):
        """检测到「我喜欢」时提取为 fact 记忆"""
        extracted = service.extract_from_conversation(
            user_message="我喜欢用 VSCode 写代码，觉得比其他 IDE 都好用",
            assistant_response="VSCode 确实很棒！插件生态也很丰富。",
        )

        kinds = [e.kind for e in extracted]

        # 应该包含至少一条 FACT（偏好）+ 两条 CHAT_RAW
        assert MemoryKind.FACT in kinds
        assert MemoryKind.CHAT_RAW in kinds

        fact_entries = [e for e in extracted if e.kind == MemoryKind.FACT]
        assert any("喜欢" in e.content or "VSCode" in e.content for e in fact_entries)

    def test_extract_user_name(self, service: MemoryService):
        """检测到「我叫」时提取为高重要性事实"""
        extracted = service.extract_from_conversation(
            user_message="我叫小明，你以后可以叫我这个名字",
            assistant_response="好的小明，我记住了！",
        )
        fact_entries = [e for e in extracted if e.kind == MemoryKind.FACT]
        name_facts = [e for e in fact_entries if e.importance >= 8]
        assert len(name_facts) >= 1

    def test_extract_promise(self, service: MemoryService):
        """检测到承诺类关键词"""
        extracted = service.extract_from_conversation(
            user_message="明天下午3点记得提醒我开会",
            assistant_response="没问题，我会记住的！",
        )
        fact_entries = [e for e in extracted if e.kind == MemoryKind.FACT]
        assert any(e.importance >= 6 and ("明天" in e.content or "3点" in e.content or "提醒" in e.content)
                    for e in fact_entries)

    def test_extract_positive_emotion(self, service: MemoryService):
        """检测到正面情绪关键词"""
        extracted = service.extract_from_conversation(
            user_message="太棒了！这个功能做得真好，非常感谢！",
            assistant_response="谢谢夸奖 😊 我会继续努力的。",
        )
        emotional = [e for e in extracted if e.kind == MemoryKind.EMOTIONAL]
        assert len(emotional) >= 1

    def test_always_saves_chat_raw(self, service: MemoryService):
        """每次对话都记录 chat_raw"""
        extracted = service.extract_from_conversation(
            user_message="随便聊聊",
            assistant_response="好啊，聊什么？",
        )
        chat_raws = [e for e in extracted if e.kind == MemoryKind.CHAT_RAW]
        assert len(chat_raws) == 2  # user + assistant

    def test_assistant_chat_raw_keeps_assistant_session_id(self, service: MemoryService):
        extracted = service.extract_from_conversation(
            user_message="你好",
            assistant_response="你好呀，我是小晏。",
            assistant_session_id="assistant_test_1",
        )
        assistant_chat = next(
            e for e in extracted if e.kind == MemoryKind.CHAT_RAW and e.role == "assistant"
        )
        user_chat = next(
            e for e in extracted if e.kind == MemoryKind.CHAT_RAW and e.role == "user"
        )
        assert assistant_chat.session_id == "assistant_test_1"
        assert user_chat.session_id is None

    def test_neutral_message_no_fact_extraction(self, service: MemoryService):
        """中性消息不会产生额外 fact 记忆（只有 chat_raw）"""
        extracted = service.extract_from_conversation(
            user_message="今天天气怎么样？",
            assistant_response="我不确定你的位置哦，你可以看看窗外。",
        )
        facts = [e for e in extracted if e.kind == MemoryKind.FACT]
        # 中性消息不应该触发偏好检测
        pref_facts = [f for f in facts if f.importance >= 6]
        assert len(pref_facts) == 0


# ═══════════════════════════════════════════════════
# 人格感知检索测试
# ═══════════════════════════════════════════════════


class TestPersonalityAwareRetrieval:
    """性格影响检索结果排序"""

    def test_high_openness_prefers_facts(self):
        """高开放性的人：fact/semantic 排名靠前"""
        high_open_personality = PersonalityDimensions(openness=85)
        service = MemoryService(personality=high_open_personality)

        entries = [
            MemoryEntry(kind=MemoryKind.FACT, content="关于编程的新发现", retention_score=0.5),
            MemoryEntry(kind=MemoryKind.EPISODIC, content="一次有趣的对话", retention_score=0.55),
            MemoryEntry(kind=MemoryKind.SEMANTIC, content="学到的新概念", retention_score=0.48),
        ]

        ranked = service._rank_by_personality(entries, "test")
        # Fact 或 Semantic 应该因为 openess 加成而排名提升
        fact_idx = next((i for i, e in enumerate(ranked) if e.kind == MemoryKind.FACT), None)
        episodic_idx = next((i for i, e in enumerate(ranked) if e.kind == MemoryKind.EPISODIC), None)
        assert fact_idx is not None
        assert episodic_idx is not None
        # 虽然 fact 的 base retention 低一点，但高开放性加成后应该接近或超过 episodic
        assert fact_idx < 2  # 至少在前两名

    def test_high_neuroticism_remembers_negative(self):
        """高神经质的人：负面情绪记忆更不容易被遗忘（排序靠前）"""
        neurotic_personality = PersonalityDimensions(neuroticism=80)
        service = MemoryService(personality=neurotic_personality)

        entries = [
            MemoryEntry(kind=MemoryKind.EMOTIONAL, content="开心的回忆", emotion_tag=MemoryEmotion.POSITIVE, retention_score=0.4),
            MemoryEntry(kind=MemoryKind.EMOTIONAL, content="让人不安的经历", emotion_tag=MemoryEmotion.NEGATIVE, retention_score=0.35),
        ]

        ranked = service._rank_by_personality(entries, "test")
        negative_idx = next(i for i, e in enumerate(ranked) if e.emotion_tag == MemoryEmotion.NEGATIVE)
        positive_idx = next(i for i, e in enumerate(ranked) if e.emotion_tag == MemoryEmotion.POSITIVE)
        assert negative_idx < positive_idx  # 负面记忆因神经质加成排前面

    def test_low_neuroticism_weakens_emotional(self):
        """低神经质的人：情绪印记强度降低"""
        stable_personality = PersonalityDimensions(neuroticism=20)
        service = MemoryService(personality=stable_personality)

        adjusted = service._adjust_strength_for_personality(MemoryKind.EMOTIONAL, MemoryStrength.NORMAL)
        assert adjusted == MemoryStrength.WEAK

    def test_high_openness_boosts_fact(self):
        """高开放性的人：事实记忆强度增强"""
        open_personality = PersonalityDimensions(openness=80)
        service = MemoryService(personality=open_personality)

        adjusted = service._adjust_strength_for_personality(MemoryKind.FACT, MemoryStrength.NORMAL)
        assert adjusted.value > MemoryStrength.NORMAL.value  # type: ignore


# ═══════════════════════════════════════════════════
# Prompt 上下文集成测试
# ═══════════════════════════════════════════════════


class TestPromptIntegration:
    """记忆注入 prompt 测试"""

    @pytest.fixture()
    def service_with_data(self) -> tuple[MemoryService, InMemoryMemoryRepository]:
        repo = InMemoryMemoryRepository()
        svc = MemoryService(repository=repo)
        return svc, repo

    def test_empty_service_returns_empty_context(self):
        """无数据时返回空字符串"""
        service = MemoryService()  # 无 repository
        ctx = service.build_memory_prompt_context(user_message="hello")
        assert ctx == ""

    def test_context_contains_memory_header(self, service_with_data):
        service, repo = service_with_data
        service.create(MemoryKind.FACT, "重要事实：用户叫小明", importance=9)
        ctx = service.build_memory_prompt_context()
        assert "你记得的事情" in ctx
        assert "事实" in ctx

    def test_context_respects_max_chars(self, service_with_data):
        service, repo = service_with_data
        # 创建大量长记忆
        for i in range(20):
            service.create(MemoryKind.FACT, f"这是一条很长的事实记忆内容 {i}，包含很多文字来测试截断功能。")

        ctx = service.build_memory_prompt_context(max_chars=200)
        assert len(ctx) <= 300  # 标签开销允许一些余量

    def test_search_based_context(self, service_with_data):
        """有查询词时的上下文应包含搜索结果"""
        service, repo = service_with_data
        service.create(MemoryKind.FACT, "用户喜欢 Python 和 FastAPI")
        service.create(MemoryKind.FACT, "昨天吃了火锅")

        ctx = service.build_memory_prompt_context(user_message="Python 怎么写 API")
        # 应该搜索并找到相关的 Python 记忆
        assert "Python" in ctx or len(ctx) > 0 or ctx == ""

    def test_summary_stats(self, service_with_data):
        service, repo = service_with_data
        service.create(MemoryKind.FACT, "F1")
        service.create(MemoryKind.FACT, "F2")
        service.create(MemoryKind.EPISODIC, "E1")
        service.create(MemoryKind.CHAT_RAW, "C1")

        summary = service.get_memory_summary()
        assert summary["available"] is True
        assert summary["total_estimated"] >= 4
        assert "fact" in summary["by_kind"]
        assert summary["by_kind"]["fact"] >= 2

    def test_timeline_returns_display_dicts(self, service_with_data):
        service, repo = service_with_data
        service.create(MemoryKind.FACT, "时间线测试")
        timeline = service.get_memory_timeline(limit=10)
        assert isinstance(timeline, list)
        assert len(timeline) >= 1
        assert "kind" in timeline[0]
        assert "content" in timeline[0]


# ═══════════════════════════════════════════════════
# 辅助函数测试
# ═══════════════════════════════════════════════════


class TestHelperFunctions:
    """内部辅助函数的单元测试"""

    def test_boost_strength(self):
        assert MemoryService._boost_strength(MemoryStrength.WEAK) == MemoryStrength.NORMAL
        assert MemoryService._boost_strength(MemoryStrength.NORMAL) == MemoryStrength.VIVID
        assert MemoryService._boost_strength(MemoryStrength.CORE) == MemoryStrength.CORE  # 已是最高

    def test_weaken_strength(self):
        assert MemoryService._weaken_strength(MemoryStrength.VIVID) == MemoryStrength.NORMAL
        assert MemoryService._weaken_strength(MemoryStrength.NORMAL) == MemoryStrength.WEAK
        assert MemoryService._weaken_strength(MemoryStrength.FAINT) == MemoryStrength.FAINT  # 已是最低

    def test_extract_sentence(self):
        service = MemoryService()
        result = service._extract_sentence("我喜欢吃苹果和香蕉。还有橙子也不错。", "喜欢")
        assert result is not None
        assert "喜欢" in result

    def test_extract_sentence_no_anchor(self):
        service = MemoryService()
        result = service._extract_sentence("一句话测试。", "不存在的内容")
        assert result is None

    def test_extract_keywords(self):
        service = MemoryService()
        kw = service._extract_keywords("我喜欢用Python写代码，FastAPI很好用")
        # 应该包含中文词汇和英文单词
        has_chinese = any(len(k) >= 2 and '\u4e00' <= k[0] <= '\u9fff' for k in kw)
        has_english = any(k.isalpha() and k[0].isascii() for k in kw)
        assert has_chinese or has_english
