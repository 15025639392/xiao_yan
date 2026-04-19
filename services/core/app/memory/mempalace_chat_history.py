from __future__ import annotations

from logging import getLogger
from typing import Callable

from app.llm.schemas import ChatMessage
from app.memory.mempalace_payloads import (
    clamp_weight,
    estimate_tokens,
    parse_exchange_document,
    parse_reasoning_state,
)

logger = getLogger(__name__)

_CHAT_EVENTS_SCAN_MIN = 200
_CHAT_EVENTS_SCAN_MAX = 5000
_CHAT_EVENTS_SCAN_MULTIPLIER = 12

GetCollection = Callable[[bool], object | None]


def build_chat_messages(
    user_message: str,
    *,
    limit: int,
    recent_weight: float | None,
    recent_loader: Callable[[int, int], list[dict]],
) -> list[ChatMessage]:
    normalized = (user_message or "").strip()
    if not normalized:
        return []

    total_turn_limit = max(1, int(limit))
    if recent_weight is None:
        turn_limit = total_turn_limit
    else:
        turn_limit = max(1, int(round(total_turn_limit * clamp_weight(recent_weight, fallback=1.0))))
    max_history_messages = turn_limit * 2
    candidate_limit = min(120, max(max_history_messages * 4, 12))
    token_budget = max(400, min(8000, turn_limit * 300))

    recent = recent_loader(candidate_limit, 0)
    selected_latest_first: list[dict] = []
    consumed_tokens = 0
    for item in recent:
        if len(selected_latest_first) >= max_history_messages:
            break

        message_text = str(item.get("content") or "")
        message_tokens = estimate_tokens(message_text)
        if selected_latest_first and consumed_tokens + message_tokens > token_budget:
            break

        selected_latest_first.append(item)
        consumed_tokens += message_tokens

    ordered_history = list(reversed(selected_latest_first))
    messages = [ChatMessage(role=item["role"], content=item["content"]) for item in ordered_history]
    messages.append(ChatMessage(role="user", content=normalized))
    return messages


def list_recent_chat_messages(
    *,
    limit: int,
    offset: int,
    event_loader: Callable[[int], list[dict]],
) -> list[dict]:
    safe_limit = max(0, int(limit))
    if safe_limit == 0:
        return []

    safe_offset = max(0, int(offset))
    target_window = max(1, safe_limit + safe_offset)
    scan_limit = min(
        _CHAT_EVENTS_SCAN_MAX,
        max(_CHAT_EVENTS_SCAN_MIN, target_window * _CHAT_EVENTS_SCAN_MULTIPLIER),
    )
    events = event_loader(scan_limit)
    if not events:
        return []

    end = len(events) - safe_offset
    if end <= 0:
        return []

    start = max(0, end - safe_limit)
    return list(reversed(events[start:end]))


def list_chat_events(
    *,
    wing: str,
    room: str,
    limit: int,
    get_collection: GetCollection,
) -> list[dict]:
    collection = get_collection(False)
    if collection is None:
        return []

    try:
        payload = collection.get(
            where={"$and": [{"wing": wing}, {"room": room}]},
            include=["documents", "metadatas"],
            limit=max(1, int(limit)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("MemPalace list chat events failed: %s", exc)
        return []

    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []
    ids = payload.get("ids") or []

    rows: list[tuple[str, str, str, str, str | None, str | None, str | None, dict | None]] = []
    for index, raw_document in enumerate(documents):
        if not isinstance(raw_document, str):
            continue
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        drawer_id = ids[index] if index < len(ids) and isinstance(ids[index], str) else f"row_{index}"
        filed_at = str(metadata.get("filed_at") or "")
        raw_session_id = metadata.get("session_id")
        session_id = str(raw_session_id).strip() if raw_session_id is not None else ""
        normalized_session_id = session_id or None
        raw_request_key = metadata.get("request_key")
        request_key = str(raw_request_key).strip() if raw_request_key is not None else ""
        normalized_request_key = request_key or None
        raw_reasoning_session_id = metadata.get("reasoning_session_id")
        reasoning_session_id = str(raw_reasoning_session_id).strip() if raw_reasoning_session_id is not None else ""
        normalized_reasoning_session_id = reasoning_session_id or None
        normalized_reasoning_state = parse_reasoning_state(metadata.get("reasoning_state"))
        if normalized_reasoning_session_id is None and isinstance(normalized_reasoning_state, dict):
            candidate_session_id = normalized_reasoning_state.get("session_id")
            if isinstance(candidate_session_id, str) and candidate_session_id.strip():
                normalized_reasoning_session_id = candidate_session_id.strip()

        user_text, assistant_text = parse_exchange_document(raw_document)
        if user_text:
            rows.append((filed_at, drawer_id, "user", user_text, normalized_session_id, normalized_request_key, None, None))
        if assistant_text:
            rows.append(
                (
                    filed_at,
                    drawer_id,
                    "assistant",
                    assistant_text,
                    normalized_session_id,
                    normalized_request_key,
                    normalized_reasoning_session_id,
                    normalized_reasoning_state,
                )
            )

        if not user_text and not assistant_text:
            compact = " ".join(raw_document.split())
            if compact:
                rows.append(
                    (
                        filed_at,
                        drawer_id,
                        "assistant",
                        compact,
                        normalized_session_id,
                        normalized_request_key,
                        normalized_reasoning_session_id,
                        normalized_reasoning_state,
                    )
                )

    rows.sort(key=lambda item: item[0])
    events: list[dict] = []
    for filed_at, drawer_id, role, content, session_id, request_key, reasoning_session_id, reasoning_state in rows:
        message_id = f"{drawer_id}:{role}:{len(events)}"
        events.append(
            {
                "id": message_id,
                "role": role,
                "content": content,
                "created_at": filed_at or None,
                "session_id": session_id,
                "request_key": request_key,
                "reasoning_session_id": reasoning_session_id if role == "assistant" else None,
                "reasoning_state": reasoning_state if role == "assistant" else None,
            }
        )
    return events
