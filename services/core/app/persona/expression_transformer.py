from __future__ import annotations

from app.persona.models import EmotionType, PersonalityDimensions


class EnhancedExpressionMapper:
    """增强的表达风格映射器（Week 2 新增）"""

    def __init__(self, personality: PersonalityDimensions, expression: "ExpressionStyle"):
        self.personality = personality
        self.formal_level = expression.formal_level
        self.sentence_style = expression.sentence_style
        self.expression_habit = expression.expression_habit

    def map_expression(
        self,
        content: str,
        emotion: EmotionType | None = None,
        context: str | None = None,
    ) -> str:
        result = self._apply_base_style(content)

        if emotion:
            result = self._apply_emotion_style(result, emotion)

        result = self._apply_expression_habit(result)

        if context:
            result = self._apply_context_adjustment(result, context)

        return result

    def _apply_base_style(self, content: str) -> str:
        result = self._adjust_formality(content, self.formal_level)
        result = self._adjust_sentence_style(result, self.sentence_style)
        return result

    def _adjust_formality(self, content: str, formal_level: str) -> str:
        from app.persona.models import FormalLevel

        if formal_level == FormalLevel.VERY_FORMAL:
            content = self._add_formal_connectors(content)
            content = self._add_polite_markers(content)
        elif formal_level in (FormalLevel.CASUAL, FormalLevel.SLANGY):
            content = self._simplify_language(content)
            if formal_level == FormalLevel.SLANGY:
                content = self._add_slang(content)

        return content

    def _adjust_sentence_style(self, content: str, sentence_style: str) -> str:
        from app.persona.models import SentenceStyle

        sentences = content.split("。")

        if sentence_style == SentenceStyle.SHORT:
            result = []
            for sentence in sentences:
                if len(sentence) > 50:
                    sub_sentences = self._split_long_sentence(sentence)
                    result.extend(sub_sentences)
                else:
                    result.append(sentence)
            return "。".join(result)

        if sentence_style == SentenceStyle.LONG:
            return self._merge_short_sentences(sentences)

        return content

    def _apply_emotion_style(self, content: str, emotion: EmotionType) -> str:
        emotion_modifiers = {
            EmotionType.JOY: self._add_joy_markers,
            EmotionType.SADNESS: self._add_sadness_markers,
            EmotionType.ANGER: self._add_anger_markers,
            EmotionType.FEAR: self._add_fear_markers,
            EmotionType.SURPRISE: self._add_surprise_markers,
            EmotionType.DISGUST: self._add_disgust_markers,
        }

        if emotion in emotion_modifiers:
            content = emotion_modifiers[emotion](content)

        return content

    def _apply_expression_habit(self, content: str) -> str:
        from app.persona.models import ExpressionHabit

        if self.expression_habit == ExpressionHabit.METAPHOR:
            content = self._add_metaphors(content)
        elif self.expression_habit == ExpressionHabit.QUESTIONING:
            content = self._add_rhetorical_questions(content)
        elif self.expression_habit == ExpressionHabit.HUMOROUS:
            content = self._add_humor(content)
        elif self.expression_habit == ExpressionHabit.GENTLE:
            content = self._soften_language(content)

        return content

    def _apply_context_adjustment(self, content: str, context: str) -> str:
        professional_keywords = ["工作", "项目", "任务", "业务", "分析", "报告"]
        casual_keywords = ["朋友", "娱乐", "游戏", "电影", "音乐", "聊天"]

        if any(kw in context for kw in professional_keywords):
            if self.formal_level not in ("very_formal", "formal"):
                content = self._add_professional_hints(content)
        elif any(kw in context for kw in casual_keywords):
            if self.formal_level not in ("casual", "slangy"):
                content = self._simplify_language(content)

        return content

    def _add_formal_connectors(self, content: str) -> str:
        lines = content.split("\n")
        result = []
        for i, line in enumerate(lines):
            if line.strip() and i % 2 == 0:
                result.append(f"因此，{line}")
            else:
                result.append(line)
        return "\n".join(result)

    def _add_polite_markers(self, content: str) -> str:
        return content

    def _simplify_language(self, content: str) -> str:
        replacements = {
            "因此": "所以",
            "此外": "另外",
            "综上所述": "总的来说",
            "值得注意的是": "需要注意的是",
        }
        for formal, informal in replacements.items():
            content = content.replace(formal, informal)
        return content

    def _add_slang(self, content: str) -> str:
        return content

    def _split_long_sentence(self, sentence: str) -> list[str]:
        parts = sentence.split("，")
        return [p.strip() for p in parts if p.strip()]

    def _merge_short_sentences(self, sentences: list[str]) -> str:
        return "。".join(s for s in sentences if s.strip())

    def _add_joy_markers(self, content: str) -> str:
        if not content.endswith(("！", "~", "～")):
            content += "！"
        return content

    def _add_sadness_markers(self, content: str) -> str:
        if not content.endswith(("...", "...")):
            content += "..."
        return content

    def _add_anger_markers(self, content: str) -> str:
        if not content.endswith("！"):
            content += "！"
        return content

    def _add_fear_markers(self, content: str) -> str:
        return content

    def _add_surprise_markers(self, content: str) -> str:
        if "?" not in content and "！" not in content:
            content += "？"
        return content

    def _add_disgust_markers(self, content: str) -> str:
        return content

    def _add_metaphors(self, content: str) -> str:
        return content

    def _add_rhetorical_questions(self, content: str) -> str:
        if "。" in content:
            content = content.replace("。", "，对吗？")
        return content

    def _add_humor(self, content: str) -> str:
        return content

    def _soften_language(self, content: str) -> str:
        lines = content.split("\n")
        result = []
        for i, line in enumerate(lines):
            if line.strip() and i % 2 == 0:
                result.append(f"我觉得{line}")
            else:
                result.append(line)
        return "\n".join(result)

    def _add_professional_hints(self, content: str) -> str:
        return content

