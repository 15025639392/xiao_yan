from __future__ import annotations

from typing import Any, Protocol

from app.platform_adapters.models import (
    CanonicalEvent,
    CanonicalUser,
    CoreDecision,
    DeliveryResult,
    PlatformAction,
    PlatformName,
)


class PlatformAdapter(Protocol):
    platform: PlatformName

    def parse_event(self, payload: dict[str, Any]) -> CanonicalEvent:
        ...

    def load_user(self, event: CanonicalEvent) -> CanonicalUser:
        ...

    def render_actions(
        self,
        event: CanonicalEvent,
        user: CanonicalUser,
        decision: CoreDecision,
    ) -> list[PlatformAction]:
        ...

    def deliver(self, actions: list[PlatformAction]) -> list[DeliveryResult]:
        ...
