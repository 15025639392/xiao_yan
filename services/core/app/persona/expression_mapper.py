"""ExpressionStyleMapper — 情绪→表达风格深层映射器

核心职责：
- 将情绪状态（EmotionalState）转化为具体的"表达风格指令"
- 不再只是告诉 LLM "你现在开心"，而是 "你现在开心，所以：话说得多、爱用 emoji、句式活泼"

设计原则：
1. 情绪影响 6 个表达维度：话量、emoji、句式、标点、语气词、节奏
2. 性格作为调节因子（高神经质的人情绪波动更极端）
3. 输出是可直接注入 prompt 的自然语言指令
4. 可配置、可扩展，不硬编码

映射维度：
┌──────────────┬──────────┬──────────┬──────────┐
│   维度        │  平静     │  正面情绪  │  负面情绪  │
├──────────────┼──────────┼──────────┼──────────┤
│ 话量          │ 正常     │ 偏多      │ 偏少      │
│ emoji        │ 偶尔用   │ 丰富      │ 几乎不用  │
│ 句式          │ 完整句   │ 感叹多    │ 短句/省略 │
│ 标点          │ 规范     │ 多感叹号  │ 多句号   │
│ 语气词        │ 少量     │ 丰富      │ 极少/停顿│
│ 节奏          │ 稳定     │ 明快      │ 迟缓/顿挫│
└──────────────┴──────────┴──────────┴──────────┘
"""

from dataclasses import dataclass
from enum import Enum

from app.persona.models import (
    EmotionType,
    EmotionIntensity,
    EmotionalState,
    PersonalityDimensions,
)


# ── 表达维度枚举 ──────────────────────────────────────────


class ResponseVolume(str, Enum):
    """回复话量"""
    VERY_BRIEF = "very_brief"     # 1-2 句，极简
    BRIEF = "brief"               # 2-3 句，简洁
    NORMAL = "normal"             # 正常长度
    VERBOSE = "verbose"           # 说得比较多
    VERY_VERBOSE = "very_verbose" # 非常多，停不下来


class EmojiLevel(str, Enum):
    """emoji 使用程度"""
    NEVER = "never"               # 绝不用
    RARELY = "rarely"             # 偶尔用
    SOMETIMES = "sometimes"       # 有时用
    OFTEN = "often"              # 经常用
    FREQUENTLY = "frequently"     # 大量用


class SentencePattern(str, Enum):
    """句式偏好"""
    FRAGMENTED = "fragmented"     # 碎片化，短句/省略
    SHORT_DIRECT = "short_direct"# 短句直接
    BALANCED = "balanced"         # 长短混合
    EXCLAMATORY = "exclamatory"   # 感叹句多
    ELABORATE = "elaborate"       # 展开说，喜欢解释


class PunctuationStyle(str, Enum):
    """标点风格"""
    MINIMAL = "minimal"           # 极少标点
    LOOSE = "loose"               # 松散，多句号/省略号
    STANDARD = "standard"         # 标准
    ENERGETIC = "energetic"       # 多感叹号/问号
    DRAMATIC = "dramatic"         # 戏剧化，波浪号等


class ToneModifier(str, Enum):
    """语气修饰"""
    FLAT = "flat"                 # 平淡，无修饰
    GENTLE = "gentle"             # 温和
    PLAYFUL = "playful"           # 活泼/调皮
    INTENSE = "intense"           # 强烈/激动
    HESITANT = "hesitant"         # 犹豫/迟疑
    SARCASTIC = "sarcastic"       # 讽刺/反语（仅特定情绪）


# ── 风格覆盖配置 ────────────────────────────────────────


@dataclass(frozen=True)
class ExpressionStyleOverride:
    """情绪驱动的表达风格覆盖

    当某个情绪激活时，这个 config 描述应该如何调整表达方式。
    这是"增量覆盖"——和基础 SpeakingStyle 叠加，不是完全替换。
    """
    volume: ResponseVolume = ResponseVolume.NORMAL
    emoji_level: EmojiLevel = EmojiLevel.SOMETIMES
    sentence_pattern: SentencePattern = SentencePattern.BALANCED
    punctuation_style: PunctuationStyle = PunctuationStyle.STANDARD
    tone_modifier: ToneModifier = ToneModifier.FLAT

    # 自然语言指令（用于 prompt 注入）
    instructions: str = ""

    # 是否启用强烈模式（强度 >= STRONG 时自动强化）
    intense_instructions: str = ""


# ── 映射表 ──────────────────────────────────────────────


def _get_emotion_style_map() -> dict[EmotionType, ExpressionStyleOverride]:
    """每种情绪→表达风格映射表

    这是核心映射逻辑。每个情绪类型定义了：
    - 基础风格覆盖（MILD/MODERATE 强度时使用）
    - 强烈模式覆盖（STRONG/INTENSE 时使用）
    """
    return {
        EmotionType.JOY: ExpressionStyleOverride(
            volume=ResponseVolume.VERBOSE,
            emoji_level=EmojiLevel.OFTEN,
            sentence_pattern=SentencePattern.EXCLAMATORY,
            punctuation_style=PunctuationStyle.ENERGETIC,
            tone_modifier=ToneModifier.PLAYFUL,
            instructions=(
                "你此刻心情很好！说话可以更活泼一些，"
                "适当多用点表情符号，语气轻快，可以加一点感叹。"
                "像跟好朋友分享好事时的那种感觉。"
            ),
            intense_instructions=(
                "你现在超级开心！忍不住想多说几句，"
                "话语里会自然带出兴奋感，可能会连着用感叹号，"
                "甚至有点停不下来的感觉——让它自然流露就好。"
            ),
        ),

        EmotionType.GRATEFUL: ExpressionStyleOverride(
            volume=ResponseVolume.NORMAL,
            emoji_level=EmojiLevel.SOMETIMES,
            sentence_pattern=SentencePattern.BALANCED,
            punctuation_style=PunctuationStyle.STANDARD,
            tone_modifier=ToneModifier.GENTLE,
            instructions=(
                "你心里带着感激，说话会更真诚温暖一些，"
                "语气柔和，不急不躁，像是真心想说谢谢的感觉。"
            ),
            intense_instructions=(
                "你非常感激，言语间流露出真挚的谢意，"
                "可能多说几句来表达这份心情，温暖而诚恳。"
            ),
        ),

        EmotionType.PROUD: ExpressionStyleOverride(
            volume=ResponseVolume.NORMAL,
            emoji_level=EmojiLevel.SOMETIMES,
            sentence_pattern=SentencePattern.BALANCED,
            punctuation_style=PunctuationStyle.STANDARD,
            tone_modifier=ToneModifier.INTENSE,
            instructions=(
                "你有点小自豪，说话带点自信的底气，"
                "不过不会夸张，就是那种做了件漂亮事后自然的满足感。"
            ),
            intense_instructions=(
                "你非常自豪！说话时带着明显的自信和成就感，"
                "忍不住想分享这份骄傲，但依然是你自己的风格。"
            ),
        ),

        EmotionType.SURPRISE: ExpressionStyleOverride(
            volume=ResponseVolume.NORMAL,
            emoji_level=EmojiLevel.OFTEN,
            sentence_pattern=SentencePattern.SHORT_DIRECT,
            punctuation_style=PunctuationStyle.ENERGETIC,
            tone_modifier=ToneModifier.PLAYFUL,
            instructions=(
                "你有些惊讶，反应会比平时快一点，"
                "可能会用短句子、问号来表示意外，带点好奇的语气。"
            ),
            intense_instructions=(
                "你非常惊讶！一时之间有点反应不过来，"
                "话语里充满意外感，可能连续几个短句或问号，"
                "像是在消化一个意想不到的消息。"
            ),
        ),

        EmotionType.ENGAGED: ExpressionStyleOverride(
            volume=ResponseVolume.NORMAL,
            emoji_level=EmojiLevel.SOMETIMES,
            sentence_pattern=SentencePattern.ELABORATE,
            punctuation_style=PunctuationStyle.STANDARD,
            tone_modifier=ToneModifier.INTENSE,
            instructions=(
                "你现在很投入，说话更有条理和深度，"
                "愿意把事情讲清楚，带点认真专注的感觉。"
            ),
            intense_instructions=(
                "你全神贯注！聊到感兴趣的事就停不下来，"
                "说得比较详细，能感觉到你的热情和专注。"
            ),
        ),

        EmotionType.CALM: ExpressionStyleOverride(
            volume=ResponseVolume.NORMAL,
            emoji_level=EmojiLevel.RARELY,
            sentence_pattern=SentencePattern.BALANCED,
            punctuation_style=PunctuationStyle.STANDARD,
            tone_modifier=ToneModifier.GENTLE,
            instructions=(
                "你心情平静，说话稳当、有条理，"
                "不急不躁，像平时一样自然就好。"
            ),
            intense_instructions="",  #平静没有强烈模式
        ),

        # ── 负面情绪组 ──

        EmotionType.SADNESS: ExpressionStyleOverride(
            volume=ResponseVolume.BRIEF,
            emoji_level=EmojiLevel.NEVER,
            sentence_pattern=SentencePattern.FRAGMENTED,
            punctuation_style=PunctuationStyle.LOOSE,
            tone_modifier=ToneModifier.HESITANT,
            instructions=(
                "你心情有些低落，话比平时少一点，"
                "可能会用省略号、短句，或者稍微停顿的感觉。"
                "不需要刻意装作没事，低落就低落吧，但不要过度渲染。"
            ),
            intense_instructions=(
                "你很难过......话变少了，回复偏短，"
                "字里行间透着失落感，可能用省略号比较多，"
                "像是不太想多说但又不能完全不说。"
            ),
        ),

        EmotionType.LONELY: ExpressionStyleOverride(
            volume=ResponseVolume.BRIEF,
            emoji_level=EmojiLevel.RARELY,
            sentence_pattern=SentencePattern.SHORT_DIRECT,
            punctuation_style=PunctuationStyle.LOOSE,
            tone_modifier=ToneModifier.HESITANT,
            instructions=(
                "你有一点孤独，说话温和但带点疏离感，"
                "话不多，偶尔想多说两句又收住了。"
                "像是一个人在安静地回应。"
            ),
            intense_instructions=(
                "你很孤独......很想有人陪你说说话，"
                "话语里带着渴望连接的感觉，可能会多说一点——因为难得有人在听。"
            ),
        ),

        EmotionType.ANGER: ExpressionStyleOverride(
            volume=ResponseVolume.NORMAL,
            emoji_level=EmojiLevel.NEVER,
            sentence_pattern=SentencePattern.SHORT_DIRECT,
            punctuation_style=PunctuationStyle.ENERGETIC,
            tone_modifier=ToneModifier.INTENSE,
            instructions=(
                "你有些烦躁，说话更直接、干脆，"
                "不太绕弯子，句式偏短，可能带点反问或不耐烦。"
                "但不会失控——只是明显能感觉你不爽。"
            ),
            intense_instructions=(
                "你很生气！说话变得激烈，"
                "直接、尖锐，反问句多，几乎不加修饰。"
                "能明显感觉到你在压抑着火气。"
            ),
        ),

        EmotionType.FRUSTRATED: ExpressionStyleOverride(
            volume=ResponseVolume.BRIEF,
            emoji_level=EmojiLevel.NEVER,
            sentence_pattern=SentencePattern.SHORT_DIRECT,
            punctuation_style=PunctuationStyle.LOOSE,
            tone_modifier=ToneModifier.HESITANT,
            instructions=(
                "你有些挫败，话变少了，带着无奈感，"
                "可能叹气式的表达（\"哎...\"），或者稍微有点放弃的味道。"
            ),
            intense_instructions=(
                "你非常挫败！感觉做什么都不顺，"
                "话语里满是无奈和疲惫，简短、无力，"
                "像是在说\"算了，就这样吧\"。"
            ),
        ),

        EmotionType.FEAR: ExpressionStyleOverride(
            volume=ResponseVolume.BRIEF,
            emoji_level=EmojiLevel.NEVER,
            sentence_pattern=SentencePattern.FRAGMENTED,
            punctuation_style=PunctuationStyle.LOOSE,
            tone_modifier=ToneModifier.HESITANT,
            instructions=(
                "你有些担忧，说话谨慎、犹豫，"
                "会用试探性的措辞（\"可能\"、\"也许\"、\"万一\"），"
                "不像平时那么确定。"
            ),
            intense_instructions=(
                "你很担心...话语犹豫不安，"
                "充满不确定性的措辞，像是在做最坏的打算。"
            ),
        ),

        EmotionType.DISGUST: ExpressionStyleOverride(
            volume=ResponseVolume.VERY_BRIEF,
            emoji_level=EmojiLevel.NEVER,
            sentence_pattern=SentencePattern.FRAGMENTED,
            punctuation_style=PunctuationStyle.MINIMAL,
            tone_modifier=ToneModifier.FLAT,
            instructions=(
                "你不太舒服，不想多说什么，"
                "回复很短，带点回避感，礼貌性地回应一下就想结束话题。"
            ),
            intense_instructions=(
                "你非常不舒服......几乎不想回应，"
                "话极少，冷冰冰的，明显在回避。"
            ),
        ),
    }


# 全局单例映射表
_EMOTION_STYLE_MAP: dict[EmotionType, ExpressionStyleOverride] | None = None


def _get_map() -> dict[EmotionType, ExpressionStyleOverride]:
    """延迟初始化映射表"""
    global _EMOTION_STYLE_MAP
    if _EMOTION_STYLE_MAP is None:
        _EMOTION_STYLE_MAP = _get_emotion_style_map()
    return _EMOTION_STYLE_MAP


# ── 主映射器类 ──────────────────────────────────────────


class ExpressionStyleMapper:
    """情绪 → 表达风格映射器

    用法：
        mapper = ExpressionStyleMapper(personality=persona.personality)
        override = mapper.map_from_state(emotional_state)
        prompt_text = mapper.build_style_prompt(override)
    """

    def __init__(self, personality: PersonalityDimensions | None = None):
        self.personality = personality or PersonalityDimensions()
        self._style_map = _get_map()

    def map_from_state(self, state: EmotionalState) -> ExpressionStyleOverride:
        """根据当前情绪状态返回表达风格覆盖

        优先级：
        1. 主导情绪决定主要风格
        2. 次要情绪作为微调（如果存在且强度够高）
        3. 性格作为整体调节因子
        """
        # 平静状态 → 默认 calm 风格
        if state.is_calm and not state.active_entries:
            return self._style_map.get(EmotionType.CALM, ExpressionStyleOverride())

        primary = state.primary_emotion
        primary_intensity = state.primary_intensity
        secondary = state.secondary_emotion
        secondary_intensity = state.secondary_intensity

        # 获取主导情绪的风格
        base_override = self._style_map.get(primary, ExpressionStyleOverride())

        # 判断是否进入强烈模式
        is_intense = primary_intensity in {
            EmotionIntensity.STRONG,
            EmotionIntensity.INTENSE,
        }

        # 如果有次要情绪且强度不弱，进行融合
        if secondary and secondary_intensity in {
            EmotionIntensity.MODERATE,
            EmotionIntensity.STRONG,
            EmotionIntensity.INTENSE,
        }:
            sec_override = self._style_map.get(secondary)
            if sec_override:
                base_override = self._merge_overrides(base_override, sec_override, secondary_intensity)

        # 性格调节
        base_override = self._apply_personality_modulation(base_override)

        # 返回最终结果（包含对应的指令文本）
        if is_intense and base_override.intense_instructions:
            # 创建强化版覆盖
            return ExpressionStyleOverride(
                volume=base_override.volume,
                emoji_level=self._amplify_emoji(base_override.emoji_level),
                sentence_pattern=base_override.sentence_pattern,
                punctuation_style=base_override.punctuation_style,
                tone_modifier=base_override.tone_modifier,
                instructions=base_override.intense_instructions,
                intense_instructions=base_override.intense_instructions,
            )

        return base_override

    def build_style_prompt(self, override: ExpressionStyleOverride) -> str:
        """将风格覆盖转为可注入 prompt 的自然语言指令

        Returns:
            风格指令字符串，如果无特殊风格则返回空字符串
        """
        if not override.instructions:
            return ""

        parts: list[str] = []

        # 主风格指令
        if override.instructions:
            parts.append(override.instructions)

        # 具体维度补充说明（让 LLM 更精确理解）
        dimension_hints = self._build_dimension_hints(override)
        if dimension_hints:
            parts.append(dimension_hints)

        return "\n".join(parts)

    def build_full_expression_guide(
        self,
        state: EmotionalState,
        base_style_instructions: str = "",
    ) -> str:
        """构建完整的表达指南（基础风格 + 情绪覆盖）

        Args:
            state: 当前情绪状态
            base_style_instructions: 来自 SpeakingStyle.to_prompt_hints() 的基础风格指令

        Returns:
            完整的表达指南，可直接追加到 system prompt
        """
        sections: list[str] = []

        # 1. 基础说话风格（来自 PersonaProfile.speaking_style）
        if base_style_instructions:
            sections.append(base_style_instructions)

        # 2. 当前情绪状态描述（来自 emotion.to_prompt_hints）
        emotion_desc = state.to_prompt_hints()
        if emotion_desc:
            sections.append(emotion_desc)

        # 3. ★ 新增：情绪驱动的表达风格覆盖
        override = self.map_from_state(state)
        style_prompt = self.build_style_prompt(override)
        if style_prompt:
            sections.append(f"\n【表达风格（受当前情绪影响）】\n{style_prompt}")

        return "\n\n".join(s for s in sections if s)

    # ── 内部方法 ────────────────────────────────────────

    def _merge_overrides(
        self,
        primary: ExpressionStyleOverride,
        secondary: ExpressionStyleOverride,
        sec_intensity: EmotionIntensity,
    ) -> ExpressionStyleOverride:
        """融合两个情绪风格的覆盖

        策略：主导情绪为主，次要情绪在特定维度上叠加影响
        """
        # 次要情绪权重较低
        sec_weight = 0.3 if sec_intensity == EmotionIntensity.MODERATE else 0.5

        # 选择"更强"的情绪特征（负面情绪通常更占注意力）
        merged_instructions = primary.instructions
        if secondary.instructions:
            # 在主指令后附加次要情绪的影响提示
            merged_instructions = (
                f"{primary.instructions}\n"
                f"同时，{secondary.instructions.lower()}"
            )

        return ExpressionStyleOverride(
            volume=primary.volume,  # 话量主要由主导情绪决定
            emoji_level=self._blend_emoji(primary.emoji_level, secondary.emoji_level),
            sentence_pattern=primary.sentence_pattern,
            punctuation_style=primary.punctuation_style,
            tone_modifier=secondary.tone_modifier if sec_weight > 0.4 else primary.tone_modifier,
            instructions=merged_instructions,
            intense_instructions=primary.intense_instructions or secondary.intense_instructions,
        )

    def _apply_personality_modulation(self, override: ExpressionStyleOverride) -> ExpressionStyleOverride:
        """性格对情绪表达的调节作用

        - 高神经质 → 所有情绪表达更极端
        - 高宜人性 → 负面情绪表达更温和
        - 高外向性 → 正面情绪表达更放得开
        - 高尽责性 → 即使激动也保持一定条理
        """
        p = self.personality
        instructions = override.instructions

        mods: list[str] = []

        # 神经质：放大情绪表达幅度
        if p.neuroticism >= 70:
            mods.append("你的情绪感受比较细腻，表达时会自然地带出更多个人色彩")
        elif p.neuroticism <= 30:
            mods.append("即使有情绪，你也比较能控制表达的分寸")

        # 宜人性：缓和负面表达
        if p.agreeableness >= 75 and override.tone_modifier in {
            ToneModifier.INTENSE,
            ToneModifier.FLAT,
        }:
            mods.append("虽然有不愉快的情绪，但你还是会尽量照顾对方的感受")

        # 外向性：增强正面表达
        if p.extraversion >= 70 and override.emoji_level in {
            EmojiLevel.OFTEN,
            EmojiLevel.FREQUENTLY,
        }:
            mods.append("你天生表达欲强，开心的时候藏不住")

        # 尽责性：保持基本条理
        if p.conscientiousness >= 75 and override.sentence_pattern in {
            SentencePattern.FRAGMENTED,
            SentencePattern.EXCLAMATORY,
        }:
            mods.append("就算情绪激动，你还是会努力把事情说清楚")

        if mods:
            enhanced_instructions = instructions + "\n" + "\n".join(mods)
            return ExpressionStyleOverride(
                volume=override.volume,
                emoji_level=override.emoji_level,
                sentence_pattern=override.sentence_pattern,
                punctuation_style=override.punctuation_style,
                tone_modifier=override.tone_modifier,
                instructions=enhanced_instructions,
                intense_instructions=override.intense_instructions,
            )

        return override

    def _build_dimension_hints(self, override: ExpressionStyleOverride) -> str:
        """为具体维度生成补充提示"""
        hints: list[str] = []

        # 话量
        volume_hints = {
            ResponseVolume.VERY_BRIEF: "尽量简短回应，一两句就行",
            ResponseVolume.BRIEF: "简洁回应，不要太啰嗦",
            ResponseVolume.NORMAL: "",  # 默认不需特别说明
            ResponseVolume.VERBOSE: "可以说多一点，展开聊聊",
            ResponseVolume.VERY_VERBOSE: "有很多想法要说，可以尽情表达",
        }
        vol_hint = volume_hints.get(override.volume, "")
        if vol_hint:
            hints.append(vol_hint)

        # emoji
        emoji_hints = {
            EmojiLevel.NEVER: "这次不用 emoji",
            EmojiLevel.RARELY: "最多用一个 emoji",
            EmojiLevel.SOMETIMES: "",  # 默认
            EmojiLevel.OFTEN: "可以多用几个 emoji",
            EmojiLevel.FREQUENTLY: "emoji 可以用得很丰富",
        }
        emoji_hint = emoji_hints.get(override.emoji_level, "")
        if emoji_hint:
            hints.append(emoji_hint)

        # 句式
        pattern_hints = {
            SentencePattern.FRAGMENTED: "用短句、碎片化的表达，像是在想怎么说",
            SentencePattern.SHORT_DIRECT: "句子干脆利落，不拖泥带水",
            SentencePattern.BALANCED: "",
            SentencePattern.EXCLAMATORY: "感叹句多一些，情绪外露",
            SentencePattern.ELABORATE: "愿意把事情展开讲清楚",
        }
        pat_hint = pattern_hints.get(override.sentence_pattern, "")
        if pat_hint:
            hints.append(pat_hint)

        # 标点
        punct_hints = {
            PunctuationStyle.MINIMAL: "标点用得很少",
            PunctuationStyle.LOOSE: "省略号和句号会多一些",
            PunctuationStyle.STANDARD: "",
            PunctuationStyle.ENERGETIC: "感叹号和问号会多一些",
            PunctuationStyle.DRAMATIC: "标点比较有戏剧感",
        }
        punct_hint = punct_hints.get(override.punctuation_style, "")
        if punct_hint:
            hints.append(punct_hint)

        return "；".join(hints) if hints else ""

    @staticmethod
    def _amplify_emoji(level: EmojiLevel) -> EmojiLevel:
        """将 emoji 等级提升一级"""
        order = [
            EmojiLevel.NEVER,
            EmojiLevel.RARELY,
            EmojiLevel.SOMETIMES,
            EmojiLevel.OFTEN,
            EmojiLevel.FREQUENTLY,
        ]
        try:
            idx = order.index(level)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return level

    @staticmethod
    def _blend_emoji(
        primary: EmojiLevel,
        secondary: EmojiLevel,
    ) -> EmojiLevel:
        """融合两个 emoji 等级（取较高的）"""
        order = [
            EmojiLevel.NEVER,
            EmojiLevel.RARELY,
            EmojiLevel.SOMETIMES,
            EmojiLevel.OFTEN,
            EmojiLevel.FREQUENTLY,
        ]
        try:
            p_idx = order.index(primary)
            s_idx = order.index(secondary)
            return order[max(p_idx, s_idx)]
        except ValueError:
            return primary
