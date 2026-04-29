from __future__ import annotations

from datetime import datetime
from logging import getLogger

logger = getLogger(__name__)


def record_visible_proactive_message(chat_memory_runtime, proactive_message: str, now: datetime) -> None:
    if chat_memory_runtime is None:
        return

    record_assistant_message = getattr(chat_memory_runtime, "record_assistant_message", None)
    if not callable(record_assistant_message):
        return

    assistant_session_id = f"assistant_proactive_{int(now.timestamp() * 1000)}"
    try:
        record_assistant_message(
            proactive_message,
            assistant_session_id,
            request_key=assistant_session_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("record visible proactive message failed: %s", exc)
