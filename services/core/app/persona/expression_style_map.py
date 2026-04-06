from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.persona.models import EmotionType


class ResponseVolume(str, Enum):
    """回复话量"""

    VERY_BRIEF = "very_brief"
    BRIEF = "brief"
    NORMAL = "normal"
    VERBOSE = "verbose"
    VERY_VERBOSE = "very_verbose"


class EmojiLevel(str, Enum):
    """emoji 使用程度"""

    NEVER = "never"
    RARELY = "rarely"
    SOMETIMES = "sometimes"
    OFTEN = "often"
    FREQUENTLY = "frequently"


class SentencePattern(str, Enum):
    """句式偏好"""

    FRAGMENTED = "fragmented"
    SHORT_DIRECT = "short_direct"
    BALANCED = "balanced"
    EXCLAMATORY = "exclamatory"
    ELABORATE = "elaborate"


class PunctuationStyle(str, Enum):
    """标点风格"""

    MINIMAL = "minimal"
    LOOSE = "loose"
    STANDARD = "standard"
    ENERGETIC = "energetic"
    DRAMATIC = "dramatic"


class ToneModifier(str, Enum):
    """语气修饰"""

    FLAT = "flat"
    GENTLE = "gentle"
    PLAYFUL = "playful"
    INTENSE = "intense"
    HESITANT = "hesitant"
    SARCASTIC = "sarcastic"


@dataclass(frozen=True)
class ExpressionStyleOverride:
    """情绪驱动的表达风格覆盖"""

    volume: ResponseVolume = ResponseVolume.NORMAL
    emoji_level: EmojiLevel = EmojiLevel.SOMETIMES
    sentence_pattern: SentencePattern = SentencePattern.BALANCED
    punctuation_style: PunctuationStyle = PunctuationStyle.STANDARD
    tone_modifier: ToneModifier = ToneModifier.FLAT
    instructions: str = ""
    intense_instructions: str = ""


def _build_emotion_style_map() -> dict[EmotionType, ExpressionStyleOverride]:
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
            intense_instructions="",
        ),
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


_EMOTION_STYLE_MAP: dict[EmotionType, ExpressionStyleOverride] | None = None


def get_emotion_style_map() -> dict[EmotionType, ExpressionStyleOverride]:
    global _EMOTION_STYLE_MAP
    if _EMOTION_STYLE_MAP is None:
        _EMOTION_STYLE_MAP = _build_emotion_style_map()
    return _EMOTION_STYLE_MAP

