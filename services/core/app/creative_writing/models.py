from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NovelCharacter(BaseModel):
    name: str
    role: str = ""
    desire: str = ""


class NovelHabitState(BaseModel):
    attachment_reason: str = ""
    last_pause: str = ""
    next_intention: str = ""
    cadence_note: str = "有余力时写一点，优先保持连续感，不追求产量。"
    updated_at: datetime = Field(default_factory=utc_now)


class NovelProject(BaseModel):
    id: str
    title: str
    premise: str
    tone: str = "细腻、克制、有持续的情绪暗流"
    habit_note: str = "这是小晏自己的长期创作习惯，不是平台发布任务。"
    habit_state: NovelHabitState = Field(default_factory=NovelHabitState)
    characters: list[NovelCharacter] = Field(default_factory=list)
    outline: list[str] = Field(default_factory=list)
    current_chapter_index: int = Field(default=1, ge=1)
    status: Literal["drafting", "paused", "finished"] = "drafting"
    folder_name: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NovelFragmentDigest(BaseModel):
    summary: str = ""
    next_intention: str = ""
    should_advance_chapter: bool = False
    chapter_closure_reason: str = ""


class NovelFragment(BaseModel):
    id: str
    project_id: str
    chapter_index: int = Field(ge=1)
    sequence: int = Field(ge=1)
    content: str
    summary: str = ""
    digest: NovelFragmentDigest | None = None
    file_path: str
    created_at: datetime = Field(default_factory=utc_now)


class NovelChapterSummary(BaseModel):
    id: str
    project_id: str
    chapter_index: int = Field(ge=1)
    title: str = ""
    summary: str
    file_path: str
    created_at: datetime = Field(default_factory=utc_now)


class NovelWritingContext(BaseModel):
    project_id: str
    chapter_index: int
    previous_chapter_summaries: list[str] = Field(default_factory=list)
    recent_summaries: list[str] = Field(default_factory=list)
    recent_excerpt: str = ""


class BeingWritingContext(BaseModel):
    time_of_day: str = ""
    energy: str = ""
    mood: str = ""
    focus_tension: str = ""
    primary_emotion: str = ""
    primary_intensity: str = ""
    mood_valence: float = 0
    arousal: float = 0


class NovelWritingImpulse(BaseModel):
    project_id: str
    title: str
    score: int = Field(ge=0)
    reasons: list[str] = Field(default_factory=list)
    next_intention: str = ""
    suggested_action: str = ""


class CreativeWritingImpulseReport(BaseModel):
    recommended_project_id: str | None = None
    impulses: list[NovelWritingImpulse] = Field(default_factory=list)
    being_context: BeingWritingContext | None = None


class NovelWritingSessionSuggestion(BaseModel):
    project_id: str
    title: str
    intention: str
    suggested_action: str
    reasons: list[str] = Field(default_factory=list)
    context: NovelWritingContext


class NovelWritingSession(BaseModel):
    id: str
    project_id: str
    title: str
    intention: str
    suggested_action: str
    reasons: list[str] = Field(default_factory=list)
    context: NovelWritingContext
    status: Literal["pending", "cancelled", "completed"] = "pending"
    completed_fragment_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CreativeWritingLibrary(BaseModel):
    projects: list[NovelProject] = Field(default_factory=list)
