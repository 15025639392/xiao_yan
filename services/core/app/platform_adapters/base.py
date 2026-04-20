from __future__ import annotations

from datetime import datetime
from hashlib import sha1
from typing import Any

from app.platform_adapters.models import (
    CanonicalEvent,
    CanonicalUser,
    CoreDecision,
    DeliveryResult,
    PlatformAction,
    PlatformName,
)


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


class BasePlatformAdapter:
    platform: PlatformName

    def load_user(self, event: CanonicalEvent) -> CanonicalUser:
        return event.user

    def deliver(self, actions: list[PlatformAction]) -> list[DeliveryResult]:
        results: list[DeliveryResult] = []
        for action in actions:
            digest = sha1(
                f"{self.platform}:{action.action_type}:{action.target_thread_id}:{action.content}".encode("utf-8")
            ).hexdigest()[:12]
            status = "drafted" if action.delivery_mode == "draft" else "simulated"
            results.append(
                DeliveryResult(
                    platform=action.platform,
                    action_type=action.action_type,
                    status=status,
                    target_thread_id=action.target_thread_id,
                    reference_id=f"{self.platform}_{digest}",
                    message=self._delivery_message(action),
                    metadata={"simulated": True},
                )
            )
        return results

    def _delivery_message(self, action: PlatformAction) -> str:
        if action.delivery_mode == "draft":
            return f"{self.platform} draft prepared"
        return f"{self.platform} simulated delivery prepared"

    def _build_action(
        self,
        *,
        event: CanonicalEvent,
        decision: CoreDecision,
        action_type: str,
        title: str | None = None,
        delivery_mode: str = "draft",
    ) -> PlatformAction:
        content = decision.primary_text
        if decision.supporting_points:
            content = "\n".join([decision.primary_text, "", *[f"- {point}" for point in decision.supporting_points]])
        return PlatformAction(
            platform=self.platform,
            action_type=action_type,  # type: ignore[arg-type]
            target_thread_id=event.thread_id,
            title=title,
            content=content,
            delivery_mode=delivery_mode,  # type: ignore[arg-type]
            metadata={"decision_kind": decision.kind, "event_type": event.event_type},
        )
