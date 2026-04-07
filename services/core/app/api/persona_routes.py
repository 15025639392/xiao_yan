from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pydantic.aliases import AliasChoices

from app.api.deps import get_goal_repository, get_memory_repository, get_persona_service, get_state_store
from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.repository import GoalRepository
from app.memory.repository import MemoryRepository
from app.persona.models import (
    ExpressionHabit,
    FormalLevel,
    PersonaProfile,
    SentenceStyle,
)
from app.persona.service import PersonaService
from app.persona.templates import PERSONA_TYPES, PersonaTemplateManager
from app.persona.validator import PersonaValidator
from app.runtime import StateStore


class PersonaUpdateRequest(BaseModel):
    name: str | None = None
    identity: str | None = None
    origin_story: str | None = None


class PersonalityUpdateRequest(BaseModel):
    openness: int | None = None
    conscientiousness: int | None = None
    extraversion: int | None = None
    agreeableness: int | None = None
    neuroticism: int | None = None


class SpeakingStyleUpdateRequest(BaseModel):
    formal_level: FormalLevel | None = None
    sentence_style: SentenceStyle | None = None
    expression_habit: ExpressionHabit | None = None
    emoji_usage: str | None = None
    verbal_tics: list[str] | None = None
    response_length: str | None = None


class PersonaFeaturesUpdateRequest(BaseModel):
    avatar_enabled: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("avatar_enabled", "desktop_pet_enabled"),
    )


class PersonaCreateFromTemplateRequest(BaseModel):
    template_type: PERSONA_TYPES = Field(..., description="选择的人格模板类型")
    customizations: dict | None = Field(None, description="自定义配置")


def build_persona_router() -> APIRouter:
    router = APIRouter()

    @router.get("/persona/templates")
    async def list_persona_templates():
        manager = PersonaTemplateManager()
        templates = manager.list_templates()
        return {
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "personality": t.personality.model_dump(),
                    "speaking_style": t.speaking_style.model_dump(),
                }
                for t in templates
            ]
        }

    @router.post("/persona/from-template")
    async def create_persona_from_template(request: PersonaCreateFromTemplateRequest):
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template(request.template_type, request.customizations)
        validator = PersonaValidator()
        report = validator.get_validation_report(persona)
        return {"persona": persona.model_dump(), "validation": report}

    @router.post("/persona/validate")
    async def validate_persona(persona: PersonaProfile):
        validator = PersonaValidator()
        report = validator.get_validation_report(persona)
        return report

    @router.get("/persona")
    def get_persona(persona_service: PersonaService = Depends(get_persona_service)) -> dict:
        profile = persona_service.get_profile()
        return profile.model_dump()

    @router.put("/persona")
    def update_persona(
        request: PersonaUpdateRequest,
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        updated = persona_service.update_profile(
            name=request.name,
            identity=request.identity,
            origin_story=request.origin_story,
        )
        return {"success": True, "profile": updated.model_dump()}

    @router.put("/persona/personality")
    def update_personality(
        request: PersonalityUpdateRequest,
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="至少需要提供一个性格维度")
        updated = persona_service.update_personality(**updates)
        return {"success": True, "profile": updated.model_dump()}

    @router.put("/persona/speaking-style")
    def update_speaking_style(
        request: SpeakingStyleUpdateRequest,
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="至少需要提供一个风格字段")
        updated = persona_service.update_speaking_style(**updates)
        return {"success": True, "profile": updated.model_dump()}

    @router.put("/persona/features")
    def update_persona_features(
        request: PersonaFeaturesUpdateRequest,
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="至少需要提供一个功能开关字段")
        updated = persona_service.update_features(**updates)
        return {"success": True, "profile": updated.model_dump()}

    @router.post("/persona/reset")
    def reset_persona(persona_service: PersonaService = Depends(get_persona_service)) -> dict:
        profile = persona_service.reset_to_default()
        return {"success": True, "profile": profile.model_dump()}

    @router.post("/persona/initialize")
    def initialize_persona(
        state_store: StateStore = Depends(get_state_store),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        persona_service: PersonaService = Depends(get_persona_service),
    ) -> dict:
        memory_count = memory_repository.clear_all()
        goal_count = goal_repository.clear_all()
        profile = persona_service.reset_to_default()
        initial_state = BeingState(
            mode=WakeMode.SLEEPING,
            focus_mode=FocusMode.SLEEPING,
            current_thought=None,
            active_goal_ids=[],
            today_plan=None,
            last_action=None,
            self_programming_job=None,
        )
        state_store.set(initial_state)
        return {
            "success": True,
            "message": "数字人已初始化",
            "cleared": {"memories": memory_count, "goals": goal_count},
            "profile": profile.model_dump(),
        }

    @router.get("/persona/emotion")
    def get_emotion_state(persona_service: PersonaService = Depends(get_persona_service)) -> dict:
        return persona_service.get_emotion_summary()

    return router
