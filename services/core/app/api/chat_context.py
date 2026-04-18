from __future__ import annotations

from dataclasses import dataclass
import re

from app.domain.models import BeingState
from app.focus.context import build_focus_context
from app.goals.repository import GoalRepository
from app.llm.schemas import ChatMessage
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.observability import KnowledgeObservabilityTracker
from app.persona.expression_mapper import ExpressionStyleMapper
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import PersonaService
from app.utils.local_time import format_local_time_context

LONG_TERM_REFERENCE_LINE_PATTERN = re.compile(
    r"^-\s+(?P<source>\S+)(?:\s+\(相似度\s+(?P<similarity>[0-9]+(?:\.[0-9]+)?)\))?\s*(?P<excerpt>.*)$"
)


@dataclass(slots=True)
class PreparedChatContext:
    focus_goal_title: str | None
    focus_context_summary: str | None
    focus_context_source_kind: str | None
    focus_context_source_label: str | None
    focus_context_reason_kind: str | None
    focus_context_reason_label: str | None
    chat_messages: list[ChatMessage]
    memory_context: str
    retrieval_failed: bool
    retrieval_attempted: bool
    persona_system_prompt: str
    expression_style_context: str | None


def prepare_chat_context(
    *,
    chat_memory_runtime: ChatMemoryRuntime,
    context_limit: int,
    goal_repository: GoalRepository,
    persona_service: PersonaService,
    state: BeingState,
    user_message: str,
) -> PreparedChatContext:
    focus_context = build_focus_context(
        state=state,
        goal_repository=goal_repository,
    )
    persona_service.infer_chat_emotion(user_message)
    persona_system_prompt = persona_service.build_system_prompt()

    current_emotion = persona_service.profile.emotion
    style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
    style_override = style_mapper.map_from_state(current_emotion)
    expression_style_context = style_mapper.build_style_prompt(style_override)

    chat_messages, memory_context, retrieval_failed, retrieval_attempted = chat_memory_runtime.resolve_context(
        user_message=user_message,
        context_limit=context_limit,
    )
    return PreparedChatContext(
        focus_goal_title=None if focus_context is None else focus_context.goal_title,
        focus_context_summary=None if focus_context is None else focus_context.render_for_prompt(),
        focus_context_source_kind=None if focus_context is None else focus_context.source_kind,
        focus_context_source_label=None if focus_context is None else focus_context.source_label,
        focus_context_reason_kind=None if focus_context is None else focus_context.reason_kind,
        focus_context_reason_label=None if focus_context is None else focus_context.reason_label,
        chat_messages=chat_messages,
        memory_context=memory_context,
        retrieval_failed=retrieval_failed,
        retrieval_attempted=retrieval_attempted,
        persona_system_prompt=persona_system_prompt,
        expression_style_context=expression_style_context or None,
    )


def build_base_chat_instructions(
    *,
    folder_permissions: list[tuple[str, str]],
    prepared: PreparedChatContext,
    state: BeingState,
    user_message: str,
    user_timezone: str | None = None,
    user_local_time: str | None = None,
    user_time_of_day: str | None = None,
) -> str:
    return build_chat_instructions(
        focus_goal_title=prepared.focus_goal_title,
        focus_context_summary=prepared.focus_context_summary,
        focus_context_source_kind=prepared.focus_context_source_kind,
        focus_context_source_label=prepared.focus_context_source_label,
        focus_context_reason_kind=prepared.focus_context_reason_kind,
        focus_context_reason_label=prepared.focus_context_reason_label,
        latest_plan_completion=None,
        user_message=user_message,
        current_thought=state.current_thought,
        persona_system_prompt=prepared.persona_system_prompt,
        relationship_summary=None,
        memory_context=prepared.memory_context or None,
        expression_style_context=prepared.expression_style_context,
        folder_permissions=folder_permissions,
        current_time_context=format_local_time_context(
            user_timezone=user_timezone,
            user_local_time=user_local_time,
            user_time_of_day=user_time_of_day,
        ),
    )


def extract_knowledge_references(memory_context: str) -> list[dict[str, str | float | None]]:
    if not memory_context:
        return []

    references: list[dict[str, str | float | None]] = []
    for line in memory_context.splitlines():
        match = LONG_TERM_REFERENCE_LINE_PATTERN.match(line.strip())
        if match is None:
            continue

        source = (match.group("source") or "").strip()
        excerpt = (match.group("excerpt") or "").strip()
        if not source or not excerpt:
            continue

        wing = source
        room = ""
        if "/" in source:
            wing, room = source.split("/", 1)

        similarity: float | None = None
        similarity_text = match.group("similarity")
        if similarity_text:
            try:
                similarity = round(float(similarity_text), 4)
            except ValueError:
                similarity = None

        references.append(
            {
                "source": source,
                "wing": wing,
                "room": room,
                "similarity": similarity,
                "excerpt": excerpt,
            }
        )

    return references


def record_retrieval_observability(
    *,
    tracker: KnowledgeObservabilityTracker | None,
    latency_ms: float,
    references: list[dict[str, str | float | None]],
    failed: bool,
) -> None:
    if tracker is None:
        return
    similarity_scores: list[float] = []
    for reference in references:
        similarity = reference.get("similarity")
        if isinstance(similarity, (int, float)):
            similarity_scores.append(float(similarity))
    tracker.record_retrieval(
        latency_ms=latency_ms,
        hit_count=len(references),
        similarity_scores=similarity_scores,
        failed=failed,
    )
