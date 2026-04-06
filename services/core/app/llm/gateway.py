import json
from collections.abc import Generator

import httpx

from app.config import LLMProviderConfig, get_chat_provider, get_llm_provider_configs
from app.llm.gateway_events import (
    extract_error_message as _extract_error_message,
    extract_output_text as _extract_output_text,
    extract_response_id as _extract_response_id,
    iter_sse_events as _iter_sse_events,
)
from app.llm.schemas import ChatMessage, ChatResult


class ChatGateway:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        wire_api: str = "responses",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.wire_api = wire_api
        self._http_client = http_client or httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0))

    @classmethod
    def from_env(cls) -> "ChatGateway":
        provider_catalog = get_llm_provider_configs()
        if not provider_catalog:
            raise RuntimeError("no llm provider is configured")

        provider_id = get_chat_provider()
        selected = next((item for item in provider_catalog if item.provider_id == provider_id), provider_catalog[0])
        return cls.from_provider_config(selected)

    @classmethod
    def from_provider_config(
        cls,
        provider_config: LLMProviderConfig,
        *,
        model: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> "ChatGateway":
        return cls(
            api_key=provider_config.api_key,
            model=(model or provider_config.default_model).strip() or provider_config.default_model,
            base_url=provider_config.base_url,
            wire_api=provider_config.wire_api,
            http_client=http_client,
        )

    @staticmethod
    def _is_minimaxi_base_url(base_url: str) -> bool:
        normalized = base_url.lower()
        return "minimaxi.com" in normalized or "minimax.chat" in normalized or "minimax" in normalized

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_chat_content(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            fragments: list[str] = []
            for part in content:
                if isinstance(part, str):
                    fragments.append(part)
                    continue
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    fragments.append(text)
            return "".join(fragments)
        return ""

    @classmethod
    def _extract_chat_text_from_response(cls, payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return ""
        message = first_choice.get("message")
        if not isinstance(message, dict):
            return ""
        return cls._extract_chat_content(message.get("content"))

    @classmethod
    def _build_chat_messages(
        cls,
        messages: list[ChatMessage],
        *,
        instructions: str | None = None,
    ) -> list[dict[str, object]]:
        system_segments: list[str] = []
        if instructions:
            system_segments.append(instructions)

        payload_messages: list[dict[str, object]] = []
        for message in messages:
            if message.role == "system":
                system_segments.append(message.content)
                continue
            payload_messages.append(message.model_dump())

        if system_segments:
            merged_system_content = "\n\n".join(segment for segment in system_segments if segment)
            if merged_system_content:
                payload_messages.insert(0, {"role": "system", "content": merged_system_content})

        return payload_messages

    @classmethod
    def _normalize_chat_tools(cls, tools: list[dict] | None) -> list[dict] | None:
        if not tools:
            return None

        normalized_tools: list[dict] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if tool.get("type") != "function":
                normalized_tools.append(tool)
                continue
            function_payload = tool.get("function")
            if isinstance(function_payload, dict):
                normalized_tools.append(tool)
                continue
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            mapped_function: dict[str, object] = {"name": name}
            description = tool.get("description")
            if isinstance(description, str) and description:
                mapped_function["description"] = description
            parameters = tool.get("parameters")
            if isinstance(parameters, dict):
                mapped_function["parameters"] = parameters
            normalized_tools.append(
                {
                    "type": "function",
                    "function": mapped_function,
                }
            )
        return normalized_tools

    @classmethod
    def _extract_response_message_text(cls, item: dict) -> str:
        content = item.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""

        fragments: list[str] = []
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                fragments.append(text)
        return "".join(fragments)

    @classmethod
    def _convert_input_items_to_chat_messages(
        cls,
        input_items: list[dict],
        *,
        instructions: str | None = None,
    ) -> list[dict[str, object]]:
        system_segments: list[str] = []
        messages: list[dict[str, object]] = []
        if instructions:
            system_segments.append(instructions)

        index = 0
        while index < len(input_items):
            item = input_items[index]
            index += 1
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            if isinstance(role, str):
                content = cls._extract_chat_content(item.get("content"))
                if role == "system":
                    if content:
                        system_segments.append(content)
                else:
                    messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )
                continue

            item_type = item.get("type")
            if item_type == "message":
                mapped_role = item.get("role", "assistant")
                content = cls._extract_response_message_text(item)
                if mapped_role == "system":
                    if content:
                        system_segments.append(content)
                else:
                    messages.append(
                        {
                            "role": mapped_role,
                            "content": content,
                        }
                    )
                continue

            if item_type == "function_call":
                tool_calls: list[dict[str, object]] = []
                current_item: dict | None = item
                while isinstance(current_item, dict) and current_item.get("type") == "function_call":
                    call_id = current_item.get("call_id")
                    function_name = current_item.get("name")
                    raw_arguments = current_item.get("arguments", "{}")
                    if isinstance(call_id, str) and isinstance(function_name, str):
                        if isinstance(raw_arguments, dict):
                            arguments = json.dumps(raw_arguments, ensure_ascii=False)
                        elif isinstance(raw_arguments, str):
                            arguments = raw_arguments
                        else:
                            arguments = "{}"

                        tool_calls.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": function_name,
                                    "arguments": arguments,
                                },
                            }
                        )

                    if index >= len(input_items):
                        break
                    next_item = input_items[index]
                    if not isinstance(next_item, dict) or next_item.get("type") != "function_call":
                        break
                    current_item = next_item
                    index += 1

                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": tool_calls,
                        }
                    )
                continue

            if item_type == "function_call_output":
                call_id = item.get("call_id")
                if not isinstance(call_id, str):
                    continue
                output = item.get("output", "")
                if isinstance(output, str):
                    output_text = output
                else:
                    output_text = json.dumps(output, ensure_ascii=False)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": output_text,
                    }
                )

        if system_segments:
            merged_system_content = "\n\n".join(segment for segment in system_segments if segment)
            if merged_system_content:
                messages.insert(0, {"role": "system", "content": merged_system_content})

        return messages

    @classmethod
    def _normalize_chat_completion_response(cls, payload: dict) -> dict:
        normalized: dict[str, object] = {"id": payload.get("id")}
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            normalized["output"] = []
            normalized["output_text"] = ""
            return normalized

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            normalized["output"] = []
            normalized["output_text"] = ""
            return normalized

        message = first_choice.get("message")
        if not isinstance(message, dict):
            normalized["output"] = []
            normalized["output_text"] = ""
            return normalized

        output_items: list[dict[str, object]] = []
        has_tool_calls = False
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                call_id = tool_call.get("id")
                function_payload = tool_call.get("function")
                if not isinstance(call_id, str) or not isinstance(function_payload, dict):
                    continue
                function_name = function_payload.get("name")
                raw_arguments = function_payload.get("arguments", "{}")
                if not isinstance(function_name, str):
                    continue
                if isinstance(raw_arguments, dict):
                    arguments = json.dumps(raw_arguments, ensure_ascii=False)
                elif isinstance(raw_arguments, str):
                    arguments = raw_arguments
                else:
                    arguments = "{}"
                output_items.append(
                    {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": function_name,
                        "arguments": arguments,
                    }
                )
                has_tool_calls = True

        content_text = cls._extract_chat_content(message.get("content"))
        if content_text and not has_tool_calls:
            output_items.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": content_text,
                        }
                    ],
                }
            )

        normalized["output"] = output_items
        normalized["output_text"] = "" if has_tool_calls else content_text
        return normalized

    def build_payload(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "input": [message.model_dump() for message in messages],
        }
        if instructions:
            payload["instructions"] = instructions
        return payload

    def create_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> ChatResult:
        if self.wire_api == "responses":
            response = self._http_client.post(
                f"{self.base_url}/responses",
                headers=self._auth_headers(),
                json=self.build_payload(messages, instructions=instructions),
            )
            response.raise_for_status()
            data = response.json()
            return ChatResult(
                response_id=data.get("id"),
                output_text=_extract_output_text(data),
            )

        if self.wire_api == "chat":
            response = self._http_client.post(
                f"{self.base_url}/chat/completions",
                headers=self._auth_headers(),
                json={
                    "model": self.model,
                    "messages": self._build_chat_messages(messages, instructions=instructions),
                },
            )
            response.raise_for_status()
            data = response.json()
            return ChatResult(
                response_id=data.get("id"),
                output_text=self._extract_chat_text_from_response(data),
            )

        raise ValueError(f"unsupported wire_api: {self.wire_api}")

    def create_response_with_tools(
        self,
        input_items: list[dict],
        *,
        instructions: str | None = None,
        tools: list[dict] | None = None,
        previous_response_id: str | None = None,
    ) -> dict:
        if self.wire_api == "responses":
            payload: dict = {
                "model": self.model,
                "input": input_items,
            }
            if instructions:
                payload["instructions"] = instructions
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            if previous_response_id:
                payload["previous_response_id"] = previous_response_id

            response = self._http_client.post(
                f"{self.base_url}/responses",
                headers=self._auth_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        if self.wire_api == "chat":
            payload = {
                "model": self.model,
                "messages": self._convert_input_items_to_chat_messages(
                    input_items,
                    instructions=instructions,
                ),
            }
            normalized_tools = self._normalize_chat_tools(tools)
            if normalized_tools:
                payload["tools"] = normalized_tools
                payload["tool_choice"] = "auto"

            response = self._http_client.post(
                f"{self.base_url}/chat/completions",
                headers=self._auth_headers(),
                json=payload,
            )
            response.raise_for_status()
            return self._normalize_chat_completion_response(response.json())

        raise ValueError(f"unsupported wire_api: {self.wire_api}")

    def list_models(self) -> list[str]:
        response = self._http_client.get(
            f"{self.base_url}/models",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_items = payload.get("data", [])
        if not isinstance(raw_items, list):
            return []

        models: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str):
                continue
            normalized = model_id.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            models.append(normalized)
        return models

    def stream_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> Generator[dict[str, str | None], None, None]:
        if self.wire_api == "responses":
            output_fragments: list[str] = []
            current_response_id: str | None = None

            with self._http_client.stream(
                "POST",
                f"{self.base_url}/responses",
                headers=self._auth_headers(),
                json=self.build_payload(messages, instructions=instructions) | {"stream": True},
            ) as response:
                response.raise_for_status()

                for event_name, event_data in _iter_sse_events(response.iter_lines()):
                    if event_data == "[DONE]":
                        break

                    payload = json.loads(event_data)

                    if event_name == "response.created":
                        current_response_id = _extract_response_id(payload) or current_response_id
                        yield {
                            "type": "response_started",
                            "response_id": current_response_id,
                        }
                        continue

                    if event_name == "response.output_text.delta":
                        delta = payload.get("delta") or ""
                        if delta:
                            output_fragments.append(delta)
                            yield {
                                "type": "text_delta",
                                "delta": delta,
                            }
                        continue

                    if event_name == "response.completed":
                        completed_response = payload.get("response", payload)
                        current_response_id = _extract_response_id(payload) or current_response_id
                        output_text = (
                            _extract_output_text(completed_response)
                            if isinstance(completed_response, dict)
                            and (completed_response.get("output") or completed_response.get("output_text"))
                            else "".join(output_fragments)
                        )
                        yield {
                            "type": "response_completed",
                            "response_id": current_response_id,
                            "output_text": output_text,
                        }
                        continue

                    if event_name == "error":
                        error_message = _extract_error_message(payload)
                        yield {
                            "type": "response_failed",
                            "error": error_message,
                        }
            return

        if self.wire_api == "chat":
            output_fragments: list[str] = []
            current_response_id: str | None = None
            started = False
            completed = False

            with self._http_client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._auth_headers(),
                json={
                    "model": self.model,
                    "messages": self._build_chat_messages(messages, instructions=instructions),
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()

                for _event_name, event_data in _iter_sse_events(response.iter_lines()):
                    if event_data == "[DONE]":
                        break

                    payload = json.loads(event_data)
                    if not isinstance(payload, dict):
                        continue

                    payload_id = payload.get("id")
                    if isinstance(payload_id, str):
                        current_response_id = payload_id
                    if current_response_id and not started:
                        started = True
                        yield {
                            "type": "response_started",
                            "response_id": current_response_id,
                        }

                    if isinstance(payload.get("error"), dict):
                        yield {
                            "type": "response_failed",
                            "error": _extract_error_message(payload),
                        }
                        completed = True
                        break

                    choices = payload.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    first_choice = choices[0]
                    if not isinstance(first_choice, dict):
                        continue
                    delta = first_choice.get("delta")
                    if isinstance(delta, dict):
                        delta_content = delta.get("content")
                        if isinstance(delta_content, str) and delta_content:
                            output_fragments.append(delta_content)
                            yield {
                                "type": "text_delta",
                                "delta": delta_content,
                            }

                    finish_reason = first_choice.get("finish_reason")
                    if isinstance(finish_reason, str) and finish_reason and not completed:
                        completed = True
                        yield {
                            "type": "response_completed",
                            "response_id": current_response_id,
                            "output_text": "".join(output_fragments),
                        }

            if not completed:
                yield {
                    "type": "response_completed",
                    "response_id": current_response_id,
                    "output_text": "".join(output_fragments),
                }
            return

        raise ValueError(f"unsupported wire_api: {self.wire_api}")

    def close(self) -> None:
        self._http_client.close()


GatewayResponse = ChatResult
from app.llm.enhanced_gateway import EnhancedChatGateway
