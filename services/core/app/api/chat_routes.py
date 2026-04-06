from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from uuid import uuid4

from app.api.deps import (
    get_chat_gateway,
    get_goal_repository,
    get_memory_repository,
    get_memory_service,
    get_persona_service,
    get_state_store,
)
from app.goals.repository import GoalRepository
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResumeRequest,
    ChatSubmissionResult,
)
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.persona.expression_mapper import ExpressionStyleMapper
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.runtime_ext.bootstrap import build_chat_messages, find_latest_today_plan_completion
from app.runtime_ext.runtime_config import get_runtime_config


def build_chat_router() -> APIRouter:
    router = APIRouter()

    def _summarize_latest_self_programming(state) -> str | None:
        job = state.self_programming_job
        if job is None:
            return None
        if job.status.value == "applied":
            return f"我补强了 {job.target_area}，并通过了验证。"
        if job.status.value == "failed":
            return f"我尝试补强 {job.target_area}，但还没通过验证。"
        return None

    def _merge_chat_stream_content(current_content: str, delta: str) -> str:
        if not current_content:
            return delta
        if not delta:
            return current_content
        if delta.startswith(current_content):
            return delta
        if current_content.startswith(delta) or delta in current_content:
            return current_content
        max_overlap = min(len(current_content), len(delta))
        for overlap in range(max_overlap, 0, -1):
            if current_content[-overlap:] == delta[:overlap]:
                return f"{current_content}{delta[overlap:]}"
        return f"{current_content}{delta}"

    def _build_resume_instruction(partial_content: str) -> str:
        return (
            "这是一次失败后的继续生成。"
            "你必须紧接着下面这段 assistant 已输出内容继续生成，"
            "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
            f"已输出内容：\n{partial_content}"
        )

    def _run_chat_submission(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
    ) -> tuple[ChatSubmissionResult, str]:
        response_id: str | None = None
        output_text = initial_output_text
        started = False
        hub = getattr(request.app.state, "realtime_hub", None)

        try:
            for event in gateway.stream_response(chat_messages, instructions=instructions):
                event_type = event["type"]
                if event_type == "response_started":
                    response_id = event.get("response_id") or response_id
                    if hub is not None and not started:
                        hub.publish_chat_started(assistant_message_id, response_id=response_id)
                        started = True
                    continue

                if event_type == "text_delta":
                    if hub is not None and not started:
                        hub.publish_chat_started(assistant_message_id, response_id=response_id)
                        started = True

                    delta = event.get("delta") or ""
                    if not delta:
                        continue

                    output_text = _merge_chat_stream_content(output_text, delta)
                    if hub is not None:
                        hub.publish_chat_delta(assistant_message_id, delta)
                    continue

                if event_type == "response_completed":
                    response_id = event.get("response_id") or response_id
                    completed_output_text = event.get("output_text") or ""
                    if completed_output_text and completed_output_text not in output_text:
                        output_text = completed_output_text
                    continue

                if event_type == "response_failed":
                    error_message = event.get("error") or "streaming failed"
                    if hub is not None:
                        hub.publish_chat_failed(assistant_message_id, error_message)
                    raise HTTPException(status_code=502, detail=error_message)
        except HTTPException:
            raise
        except Exception as exception:
            if hub is not None:
                hub.publish_chat_failed(assistant_message_id, str(exception))
            raise HTTPException(status_code=502, detail=str(exception)) from exception

        if hub is not None and not started:
            hub.publish_chat_started(assistant_message_id, response_id=response_id)
        if hub is not None:
            hub.publish_chat_completed(assistant_message_id, response_id, output_text)

        return (
            ChatSubmissionResult(
                response_id=response_id,
                assistant_message_id=assistant_message_id,
            ),
            output_text,
        )

    @router.post("/chat")
    def chat(
        request_body: ChatRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
        latest_plan_completion = find_latest_today_plan_completion(memory_repository)
        latest_self_programming = _summarize_latest_self_programming(state)

        persona_system_prompt = persona_service.build_system_prompt()
        persona_service.infer_chat_emotion(request_body.message)

        memory_context = memory_service.build_memory_prompt_context(
            user_message=request_body.message,
            max_chars=600,
        )

        current_emotion = persona_service.profile.emotion
        style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
        style_override = style_mapper.map_from_state(current_emotion)
        expression_style_context = style_mapper.build_style_prompt(style_override)

        config = get_runtime_config()
        chat_messages = build_chat_messages(
            memory_repository,
            state_store,
            goal_repository,
            request_body.message,
            limit=config.chat_context_limit,
        )
        instructions = build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_programming=latest_self_programming,
            user_message=request_body.message,
            persona_system_prompt=persona_system_prompt,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
        )

        assistant_message_id = f"assistant_{uuid4().hex}"
        submission, output_text = _run_chat_submission(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=instructions,
            assistant_message_id=assistant_message_id,
        )

        extracted = memory_service.extract_from_conversation(
            user_message=request_body.message,
            assistant_response=output_text,
            assistant_session_id=assistant_message_id,
        )
        for entry in extracted:
            memory_service.save(entry)

        return submission

    @router.post("/chat/resume")
    def resume_chat(
        request_body: ChatResumeRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
        latest_plan_completion = find_latest_today_plan_completion(memory_repository)
        latest_self_programming = _summarize_latest_self_programming(state)

        persona_system_prompt = persona_service.build_system_prompt()
        persona_service.infer_chat_emotion(request_body.message)
        memory_context = memory_service.build_memory_prompt_context(
            user_message=request_body.message,
            max_chars=600,
        )
        current_emotion = persona_service.profile.emotion
        style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
        style_override = style_mapper.map_from_state(current_emotion)
        expression_style_context = style_mapper.build_style_prompt(style_override)

        config = get_runtime_config()
        chat_messages = build_chat_messages(
            memory_repository,
            state_store,
            goal_repository,
            request_body.message,
            limit=config.chat_context_limit,
        )
        instructions = build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_programming=latest_self_programming,
            user_message=request_body.message,
            persona_system_prompt=persona_system_prompt,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
        )
        instructions = f"{instructions}\n\n{_build_resume_instruction(request_body.partial_content)}"

        submission, output_text = _run_chat_submission(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=instructions,
            assistant_message_id=request_body.assistant_message_id,
            initial_output_text=request_body.partial_content,
        )

        extracted = memory_service.extract_from_conversation(
            user_message=request_body.message,
            assistant_response=output_text,
            assistant_session_id=request_body.assistant_message_id,
        )
        for entry in extracted:
            memory_service.save(entry)

        return submission

    return router
