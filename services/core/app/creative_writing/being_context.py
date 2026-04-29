from __future__ import annotations

from app.creative_writing.models import BeingWritingContext
from app.persona.service import PersonaService
from app.world.repository import WorldRepository


def build_being_writing_context(
    *,
    persona_service: PersonaService,
    world_repository: WorldRepository | None = None,
) -> BeingWritingContext:
    emotion = persona_service.get_emotion_summary()
    world_state = world_repository.get_world_state() if world_repository is not None else None
    return BeingWritingContext(
        time_of_day=world_state.time_of_day if world_state else "",
        energy=world_state.energy if world_state else "",
        mood=world_state.mood if world_state else "",
        focus_tension=world_state.focus_tension if world_state else "",
        primary_emotion=str(emotion.get("primary_emotion", "")),
        primary_intensity=str(emotion.get("primary_intensity", "")),
        mood_valence=float(emotion.get("mood_valence", 0) or 0),
        arousal=float(emotion.get("arousal", 0) or 0),
    )
