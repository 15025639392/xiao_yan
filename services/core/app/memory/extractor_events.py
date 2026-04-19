from __future__ import annotations

from datetime import datetime, timezone

from app.memory.models import MemoryEvent


def build_memory_event(
    *,
    kind: str,
    content: str,
    role: str,
    context: dict | None,
    source_context: str | None = None,
    facet: str | None = None,
    tags: list[str] | None = None,
) -> MemoryEvent:
    source_ref, version_tag, visibility, normalized_tags = resolve_metadata(
        context=context,
        role=role,
        tags=tags or [],
    )
    return MemoryEvent(
        kind=kind,
        content=content,
        role=role,
        created_at=datetime.now(timezone.utc),
        source_context=source_context,
        facet=facet,
        tags=normalized_tags,
        source_ref=source_ref,
        version_tag=version_tag,
        governance_source="auto_extracted",
        review_status="pending_review",
        visibility=visibility,
    )


def resolve_metadata(
    *,
    context: dict | None,
    role: str,
    tags: list[str],
) -> tuple[str, str, str, list[str]]:
    context = context or {}

    raw_source_ref = context.get("source_ref")
    source_ref = str(raw_source_ref).strip() if raw_source_ref else ""
    if not source_ref:
        source_ref = default_source_ref(context=context)

    raw_version_tag = context.get("version_tag")
    version_tag = str(raw_version_tag).strip() if raw_version_tag else "v1"

    raw_visibility = str(context.get("visibility") or "").strip().lower()
    visibility = raw_visibility if raw_visibility in {"internal", "user"} else "internal"

    context_tags: list[str] = [f"role:{role}"]
    topic = context.get("topic")
    if topic:
        context_tags.append(f"topic:{str(topic).strip()}")

    normalized_tags = normalize_tags(tags + context_tags)
    return source_ref, version_tag, visibility, normalized_tags


def default_source_ref(*, context: dict) -> str:
    timestamp = str(context.get("timestamp") or "").strip()
    if timestamp:
        return f"dialogue://{timestamp}"
    return "dialogue://runtime"


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_tag in tags:
        tag = str(raw_tag).strip().lower()
        if not tag:
            continue
        if tag not in normalized:
            normalized.append(tag)
    return normalized


def pick_richer_event(left: MemoryEvent, right: MemoryEvent) -> MemoryEvent:
    def score(event: MemoryEvent) -> int:
        return (
            int(bool(event.source_ref))
            + int(bool(event.source_context))
            + int(bool(event.facet))
            + len(event.tags or [])
            + int(bool(event.version_tag))
        )

    return right if score(right) > score(left) else left
