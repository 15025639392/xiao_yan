from __future__ import annotations

from app.platform_adapters.core_decision_mapper import CoreDecisionMapper
from app.platform_adapters.models import (
    CoreDecision,
    CoreDecisionDraft,
    InternalDecisionInput,
    PlatformProcessResult,
)
from app.platform_adapters.registry import PlatformAdapterRegistry


class PlatformAdapterService:
    def __init__(
        self,
        registry: PlatformAdapterRegistry,
        decision_mapper: CoreDecisionMapper | None = None,
    ) -> None:
        self._registry = registry
        self._decision_mapper = decision_mapper or CoreDecisionMapper()

    def list_platforms(self) -> list[str]:
        return self._registry.list_platforms()

    def parse_event(self, *, platform: str, raw_payload: dict):
        adapter = self._registry.get(platform)
        return adapter.parse_event(raw_payload)

    def process(
        self,
        *,
        platform: str,
        raw_payload: dict,
        decision: CoreDecision,
    ) -> PlatformProcessResult:
        adapter = self._registry.get(platform)
        event = adapter.parse_event(raw_payload)
        user = adapter.load_user(event)
        actions = adapter.render_actions(event, user, decision)
        delivery_results = adapter.deliver(actions)
        return PlatformProcessResult(
            event=event,
            user=user,
            actions=actions,
            delivery_results=delivery_results,
        )

    def process_internal_decision(
        self,
        *,
        platform: str,
        raw_payload: dict,
        decision_input: InternalDecisionInput | dict,
    ) -> PlatformProcessResult:
        adapter = self._registry.get(platform)
        event = adapter.parse_event(raw_payload)
        user = adapter.load_user(event)
        normalized_input = (
            decision_input
            if isinstance(decision_input, InternalDecisionInput)
            else InternalDecisionInput.model_validate(decision_input)
        )
        decision = self._decision_mapper.map_from_internal(
            platform=platform,
            event=event,
            decision_input=normalized_input,
        )
        actions = adapter.render_actions(event, user, decision)
        delivery_results = adapter.deliver(actions)
        return PlatformProcessResult(
            event=event,
            user=user,
            actions=actions,
            delivery_results=delivery_results,
        )

    def process_decision_draft(
        self,
        *,
        platform: str,
        raw_payload: dict,
        decision_draft: CoreDecisionDraft | dict,
    ) -> PlatformProcessResult:
        adapter = self._registry.get(platform)
        event = adapter.parse_event(raw_payload)
        user = adapter.load_user(event)
        normalized_draft = (
            decision_draft
            if isinstance(decision_draft, CoreDecisionDraft)
            else CoreDecisionDraft.model_validate(decision_draft)
        )
        decision = self._decision_mapper.map_from_draft(decision_draft=normalized_draft)
        actions = adapter.render_actions(event, user, decision)
        delivery_results = adapter.deliver(actions)
        return PlatformProcessResult(
            event=event,
            user=user,
            actions=actions,
            delivery_results=delivery_results,
        )
