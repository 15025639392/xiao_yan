from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from typing import Callable

from app.memory.mempalace_payloads import clamp_weight, compact_text, format_similarity

logger = getLogger(__name__)

SearchBackend = Callable[[str, str, int], dict]
GetCollection = Callable[[bool], object | None]


def resolve_search_limit(default_limit: int, max_hits: int | None) -> int:
    if max_hits is None:
        return default_limit
    try:
        parsed = int(max_hits)
    except (TypeError, ValueError):
        return default_limit
    if parsed <= 0:
        return 0
    return max(1, min(default_limit, parsed))


def search_context(
    query: str,
    *,
    room: str,
    palace_path: str,
    results_limit: int,
    search_backend: SearchBackend,
    exclude_current_room: bool,
    max_hits: int | None,
    retrieval_weight: float | None,
) -> str:
    normalized = (query or "").strip()
    if not normalized:
        return ""

    if retrieval_weight is not None and clamp_weight(retrieval_weight, fallback=0.0) <= 0:
        return ""

    search_limit = resolve_search_limit(results_limit, max_hits)
    if search_limit <= 0:
        return ""

    try:
        payload = search_backend(normalized, palace_path, search_limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MemPalace search failed: %s", exc)
        return ""

    if not isinstance(payload, dict):
        return ""
    if payload.get("error"):
        logger.warning("MemPalace search returned error payload: %s", payload.get("error"))
        return ""

    raw_hits = payload.get("results")
    if not isinstance(raw_hits, list) or not raw_hits:
        return ""

    if exclude_current_room:
        filtered_hits: list[dict] = []
        for raw_hit in raw_hits:
            if not isinstance(raw_hit, dict):
                continue
            hit_room = str(raw_hit.get("room") or "").strip()
            if hit_room == room:
                continue
            filtered_hits.append(raw_hit)
        raw_hits = filtered_hits
        if not raw_hits:
            return ""

    lines = ["【长期记忆检索】"]
    for raw_hit in raw_hits[:search_limit]:
        if not isinstance(raw_hit, dict):
            continue
        text = compact_text(raw_hit.get("text") or "", 160)
        if not text:
            continue

        hit_wing = str(raw_hit.get("wing") or "unknown")
        hit_room = str(raw_hit.get("room") or "unknown")
        similarity = format_similarity(raw_hit.get("similarity"))
        lines.append(f"- {hit_wing}/{hit_room} (相似度 {similarity}) {text}")

    return "\n".join(lines) if len(lines) > 1 else ""


def has_cross_room_long_term_sources(
    *,
    wing: str,
    room: str,
    get_collection: GetCollection,
    cached_at: datetime | None,
    cached_result: bool,
    cache_seconds: int,
) -> tuple[bool, datetime, bool]:
    now = datetime.now(timezone.utc)
    ttl = max(1, int(cache_seconds))
    if cached_at is not None and (now - cached_at).total_seconds() < ttl:
        return cached_result, cached_at, cached_result

    has_sources = False
    collection = get_collection(False)
    if collection is not None:
        try:
            payload = collection.get(
                where={"wing": wing},
                include=["metadatas"],
                limit=5000,
            )
            metadatas = payload.get("metadatas") if isinstance(payload, dict) else None
            if isinstance(metadatas, list):
                ignored_rooms = {room, f"{room}_events"}
                for metadata in metadatas:
                    if not isinstance(metadata, dict):
                        continue
                    source_room = str(metadata.get("room") or "").strip()
                    if not source_room or source_room in ignored_rooms:
                        continue
                    has_sources = True
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace cross-room source scan failed: %s", exc)

    return has_sources, now, has_sources
