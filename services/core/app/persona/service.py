"""PersonaService — 人格档案管理服务

职责：
- 加载/保存人格档案（JSON 持久化）
- 提供人格 CRUD 操作
- 作为情绪引擎的统一入口
- 生成人格感知的 prompt
"""

from pathlib import Path
from datetime import datetime, timezone
from logging import getLogger
from typing import Protocol

from app.persona.models import (
    EmotionEntry,
    EmotionIntensity,
    EmotionalState,
    EmotionType,
    PersonaProfile,
    default_persona,
)
from app.persona.emotion_engine import EmotionEngine

logger = getLogger(__name__)


class PersonaRepository(Protocol):
    """人格持久化的抽象接口"""
    def save(self, profile: PersonaProfile) -> None: ...
    def load(self) -> PersonaProfile | None: ...


class FilePersonaRepository:
    """基于文件的人格持久化"""
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def save(self, profile: PersonaProfile) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))

    def load(self) -> PersonaProfile | None:
        if not self.storage_path.exists():
            return None
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = f.read()
            return PersonaProfile.model_validate_json(data)
        except Exception as exc:
            logger.warning("Failed to load persona from %s: %s", self.storage_path, exc)
            return None


class InMemoryPersonaRepository:
    """内存中的人格存储（测试用）"""
    def __init__(self) -> None:
        self._profile: PersonaProfile | None = None

    def save(self, profile: PersonaProfile) -> None:
        self._profile = profile

    def load(self) -> PersonaProfile | None:
        return self._profile


class PersonaService:
    """人格服务的统一门面

    所有关于数字人人格的操作都通过这个类进行：
    - 获取/更新人格配置
    - 触发情绪变化
    - 获取人格感知的 system prompt
    - 时间推进 (tick)
    """

    def __init__(
        self,
        repository: PersonaRepository | None = None,
        profile: PersonaProfile | None = None,
    ) -> None:
        self.repository = repository
        self._profile: PersonaProfile | None = profile
        # 延迟创建引擎（需要 personality 配置）
        self._engine: EmotionEngine | None = None

    @property
    def profile(self) -> PersonaProfile:
        """获取当前人格档案，自动加载或使用默认值"""
        if self._profile is not None:
            return self._profile
        if self.repository is not None:
            loaded = self.repository.load()
            if loaded is not None:
                self._profile = loaded
                return loaded
        # 使用默认人格
        self._profile = default_persona()
        if self.repository is not None:
            self._save_silent(self._profile)
        return self._profile

    @property
    def engine(self) -> EmotionEngine:
        """获取情绪引擎"""
        if self._engine is None:
            self._engine = EmotionEngine(personality=self.profile.personality)
        return self._engine

    # ── CRUD 操作 ──────────────────────────────────────

    def get_profile(self) -> PersonaProfile:
        """获取完整人格档案"""
        return self.profile

    def update_profile(
        self,
        name: str | None = None,
        identity: str | None = None,
        origin_story: str | None = None,
        **kwargs,
    ) -> PersonaProfile:
        """更新人格档案的基础字段"""
        current = self.profile
        updates: dict = {}
        if name is not None:
            updates["name"] = name
        if identity is not None:
            updates["identity"] = identity
        if origin_story is not None:
            updates["origin_story"] = origin_origin_story = origin_story
        updates.update(kwargs)

        updated = current.model_copy(update=updates)
        updated.version += 1
        self._profile = updated
        self._persist(updated)
        return updated

    def update_personality(self, **dimensions) -> PersonaProfile:
        """更新性格维度"""
        current = self.profile
        new_personality = current.personality.model_copy(update=dimensions)
        updated = current.model_copy(update={"personality": new_personality, "version": current.version + 1})
        self._profile = updated
        # 更新情绪引擎
        self._engine = EmotionEngine(personality=new_personality)
        self._persist(updated)
        return updated

    def update_speaking_style(self, **style_kwargs) -> PersonaProfile:
        """更新说话风格"""
        current = self.profile
        new_style = current.speaking_style.model_copy(update=style_kwargs)
        updated = current.model_copy(update={"speaking_style": new_style, "version": current.version + 1})
        self._profile = updated
        self._persist(updated)
        return updated

    def reset_to_default(self) -> PersonaProfile:
        """重置为默认人格"""
        self._profile = default_persona()
        self._engine = EmotionEngine(personality=self._profile.personality)
        self._persist(self._profile)
        return self._profile

    # ── 情绪操作 ────────────────────────────────────────

    def apply_emotion(
        self,
        emotion_type: EmotionType,
        intensity: EmotionIntensity,
        reason: str = "",
        source: str = "system",
    ) -> EmotionalState:
        """触发一个情绪事件"""
        current = self.profile.emotion
        new_emotion = self.engine.apply_event(
            current,
            emotion_type=emotion_type,
            intensity=intensity,
            reason=reason,
            source=source,
        )
        self._update_emotion(new_emotion)
        return new_emotion

    def tick_emotion(self) -> EmotionalState:
        """时间推进：衰减情绪"""
        current = self.profile.emotion
        new_emotion = self.engine.tick(current)
        self._update_emotion(new_emotion)
        return new_emotion

    def infer_chat_emotion(self, user_message: str, is_positive: bool | None = None) -> EmotionalState:
        """从聊天消息推断并应用情绪变化"""
        current = self.profile.emotion
        new_emotion = self.engine.infer_from_chat(current, user_message, is_positive)
        self._update_emotion(new_emotion)
        return new_emotion

    def infer_goal_emotion(self, event_type: str, goal_title: str) -> EmotionalState:
        """从目标事件推断并应用情绪变化"""
        current = self.profile.emotion
        new_emotion = self.engine.infer_from_goal_event(current, event_type, goal_title)
        self._update_emotion(new_emotion)
        return new_emotion

    def infer_self_improvement_emotion(self, event_type: str, target_area: str) -> EmotionalState:
        """从自编程事件推断并应用情绪变化"""
        current = self.profile.emotion
        new_emotion = self.engine.infer_from_self_improvement(current, event_type, target_area)
        self._update_emotion(new_emotion)
        return new_emotion

    # ── Prompt 生成 ──────────────────────────────────────

    def build_system_prompt(self) -> str:
        """构建人格感知的完整 system prompt"""
        return self.profile.build_system_prompt()

    def get_emotion_summary(self) -> dict:
        """获取当前情绪摘要"""
        e = self.profile.emotion
        return {
            "primary_emotion": e.primary_emotion.value,
            "primary_intensity": e.primary_intensity.value,
            "secondary_emotion": e.secondary_emotion.value if e.secondary_emotion else None,
            "secondary_intensity": e.secondary_intensity.value,
            "mood_valence": round(e.mood_valence, 3),
            "arousal": round(e.arousal, 3),
            "is_calm": e.is_calm,
            "active_entry_count": len(e.active_entries),
            "active_entries": [
                {
                    "emotion_type": entry.emotion_type.value,
                    "intensity": entry.intensity.value,
                    "reason": entry.reason,
                    "source": entry.source,
                }
                for entry in e.active_entries[-5:]  # 最近 5 条
            ],
            "last_updated": e.last_updated.isoformat() if e.last_updated else None,
        }

    # ── 内部方法 ────────────────────────────────────────

    def _update_emotion(self, new_emotion: EmotionalState) -> None:
        """更新情绪状态并持久化"""
        current = self.profile
        updated = current.model_copy(update={"emotion": new_emotion})
        self._profile = updated
        self._persist(updated)

    def _persist(self, profile: PersonaProfile) -> None:
        """持久化到存储"""
        if self.repository is not None:
            try:
                self.repository.save(profile)
            except Exception as exc:
                logger.warning("Failed to persist persona: %s", exc)

    def _save_silent(self, profile: PersonaProfile) -> None:
        """静默保存（不记录警告）"""
        if self.repository is not None:
            try:
                self.repository.save(profile)
            except Exception:
                pass
