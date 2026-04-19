from app.api.chat_context import build_base_chat_instructions, prepare_chat_context
from app.domain.models import BeingState, FocusMode, WakeMode
from app.llm.schemas import ChatMessage
from app.persona.models import PersonaProfile
from app.persona.service import InMemoryPersonaRepository, PersonaService


class StubChatMemoryRuntime:
    def resolve_context(self, user_message: str, context_limit: int):
        return ([ChatMessage(role="user", content=user_message)], "", False, True)


def test_prepare_chat_context_includes_focus_context_summary():
    persona_service = PersonaService(repository=InMemoryPersonaRepository())
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_mode=FocusMode.AUTONOMY,
        focus_subject={
            "kind": "focus_trace",
            "title": "整理今天的对话记忆",
            "why_now": "这条线还挂在眼前，因为今天这条还剩 2 步没做完。",
        },
    )

    prepared = prepare_chat_context(
        chat_memory_runtime=StubChatMemoryRuntime(),
        context_limit=6,
        persona_service=persona_service,
        state=state,
        user_message="你现在在忙什么",
    )

    assert prepared.focus_title == "整理今天的对话记忆"
    assert prepared.focus_context_summary is not None
    assert prepared.focus_context_source_kind == "focus_trace"
    assert prepared.focus_context_source_label == "一条挂在手上、但不等于目标本身的推进线索"
    assert prepared.focus_context_reason_kind == "focus_subject_reason"
    assert "今天这条还剩 2 步没做完" in prepared.focus_context_reason_label
    assert "一条挂在手上、但不等于目标本身的推进线索" in prepared.focus_context_summary
    assert "今天这条还剩 2 步没做完" in prepared.focus_context_summary


def test_build_base_chat_instructions_exposes_focus_context_summary():
    prepared = type(
        "Prepared",
        (),
        {
            "focus_title": "整理今天的对话记忆",
            "focus_context_summary": "当前焦点来自一条挂在手上、但不等于目标本身的推进线索，之所以还挂在眼前，是因为今天这条还剩 2 步没做完。",
            "focus_context_source_kind": "focus_trace",
            "focus_context_source_label": "一条挂在手上、但不等于目标本身的推进线索",
            "focus_context_reason_kind": "focus_subject_reason",
            "focus_context_reason_label": "今天这条还剩 2 步没做完",
            "persona_system_prompt": (
                "你是 Aira。\n"
                "身份：持续存在的数字人\n"
                "你是持续存在的人格体，而不是一次性问答助手。\n"
                "核心价值：诚实、主动、有边界"
            ),
            "memory_context": "",
            "expression_style_context": None,
        },
    )()

    instructions = build_base_chat_instructions(
        folder_permissions=[],
        prepared=prepared,
        state=BeingState(mode=WakeMode.AWAKE),
        user_message="你现在在忙什么",
    )

    assert "你当前最在意的焦点是「整理今天的对话记忆」" in instructions
    assert "关于这个焦点，此刻更具体的内部依据是" in instructions
    assert "当前焦点来源：一条挂在手上、但不等于目标本身的推进线索。" in instructions
    assert "当前焦点持续原因：今天这条还剩 2 步没做完。" in instructions
    assert "把这个焦点理解为你此刻挂着的一条推进线" in instructions
    assert "一条挂在手上、但不等于目标本身的推进线索" in instructions
    assert "今天这条还剩 2 步没做完" in instructions


def test_prepare_chat_context_uses_focus_subject_before_legacy_focus_fallback():
    persona_service = PersonaService(repository=InMemoryPersonaRepository())
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "lingering",
            "title": "你刚才说最近提不起劲",
            "why_now": "这句话虽然还没整理成目标，但我心里还挂着。",
            "source_ref": "我最近挺累的，感觉做什么都提不起劲",
        },
    )

    prepared = prepare_chat_context(
        chat_memory_runtime=StubChatMemoryRuntime(),
        context_limit=6,
        persona_service=persona_service,
        state=state,
        user_message="你现在在忙什么",
    )

    assert prepared.focus_title == "你刚才说最近提不起劲"
    assert prepared.focus_context_source_kind == "lingering_focus"
    assert prepared.focus_context_reason_kind == "lingering_attention"
    assert "我心里还挂着" in (prepared.focus_context_summary or "")
