from __future__ import annotations


class ChatSubmissionEvents:
    def __init__(
        self,
        *,
        hub: object | None,
        assistant_message_id: str,
        request_key: str | None,
        reasoning_session_id: str | None,
        reasoning_payload: dict | None,
        suppress_started_event: bool = False,
    ) -> None:
        self.hub = hub
        self.assistant_message_id = assistant_message_id
        self.request_key = request_key
        self.reasoning_session_id = reasoning_session_id
        self.reasoning_payload = reasoning_payload
        self.suppress_started_event = suppress_started_event
        self.started = False

    def publish_started(self, response_id: str | None) -> None:
        if self.hub is None or self.started or self.suppress_started_event:
            return
        self.hub.publish_chat_started(
            self.assistant_message_id,
            response_id=response_id,
            request_key=self.request_key,
            reasoning_session_id=self.reasoning_session_id,
            reasoning_state=self.reasoning_payload,
        )
        self.started = True

    def publish_delta(self, delta: str, *, response_id: str | None = None) -> None:
        if not delta:
            return
        self.publish_started(response_id)
        if self.hub is None:
            return
        self.hub.publish_chat_delta(
            self.assistant_message_id,
            delta,
            request_key=self.request_key,
            reasoning_session_id=self.reasoning_session_id,
            reasoning_state=self.reasoning_payload,
        )

    def publish_completed(
        self,
        *,
        response_id: str | None,
        output_text: str,
        memory_references: list[dict[str, str | float | None]] | None,
    ) -> None:
        self.publish_started(response_id)
        if self.hub is None:
            return
        self.hub.publish_chat_completed(
            self.assistant_message_id,
            response_id,
            output_text,
            request_key=self.request_key,
            memory_references=memory_references,
            reasoning_session_id=self.reasoning_session_id,
            reasoning_state=self.reasoning_payload,
        )

    def publish_failed(self, error: str, *, only_if_started: bool = False) -> None:
        if self.hub is None:
            return
        if only_if_started and not self.started:
            return
        self.hub.publish_chat_failed(
            self.assistant_message_id,
            error,
            request_key=self.request_key,
            reasoning_session_id=self.reasoning_session_id,
            reasoning_state=self.reasoning_payload,
        )
