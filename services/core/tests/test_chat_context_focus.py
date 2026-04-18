from app.api.chat_context import build_base_chat_instructions, prepare_chat_context
from app.domain.models import BeingState, FocusMode, TodayPlan, TodayPlanStep, WakeMode
from app.goals.models import Goal, GoalAdmissionMeta
from app.goals.repository import InMemoryGoalRepository
from app.llm.schemas import ChatMessage
from app.persona.models import PersonaProfile
from app.persona.service import InMemoryPersonaRepository, PersonaService


class StubChatMemoryRuntime:
    def resolve_context(self, user_message: str, context_limit: int):
        return ([ChatMessage(role="user", content=user_message)], "", False, True)


def test_prepare_chat_context_includes_focus_context_summary():
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(
        Goal(
            id="goal-1",
            title="整理今天的对话记忆",
            source="你现在在忙什么",
            admission=GoalAdmissionMeta(
                score=0.82,
                recommended_decision="admit",
                applied_decision="admit",
                reason="user_score",
            ),
        )
    )
    persona_service = PersonaService(repository=InMemoryPersonaRepository())
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_mode=FocusMode.MORNING_PLAN,
        active_goal_ids=[goal.id],
        today_plan=TodayPlan(
            goal_id=goal.id,
            goal_title=goal.title,
            steps=[
                TodayPlanStep(content="回看昨天的对话"),
                TodayPlanStep(content="整理关键线索"),
            ],
        ),
    )

    prepared = prepare_chat_context(
        chat_memory_runtime=StubChatMemoryRuntime(),
        context_limit=6,
        goal_repository=goal_repository,
        persona_service=persona_service,
        state=state,
        user_message="你现在在忙什么",
    )

    assert prepared.focus_goal_title == "整理今天的对话记忆"
    assert prepared.focus_context_summary is not None
    assert prepared.focus_context_source_kind == "user_topic_goal"
    assert prepared.focus_context_source_label == "刚接住你这轮话题的事"
    assert prepared.focus_context_reason_kind == "today_plan_pending"
    assert prepared.focus_context_reason_label == "今天这条还剩 2 步没做完"
    assert "刚接住你这轮话题的事" in prepared.focus_context_summary
    assert "今天这条还剩 2 步没做完" in prepared.focus_context_summary


def test_build_base_chat_instructions_exposes_focus_context_summary():
    prepared = type(
        "Prepared",
        (),
        {
            "focus_goal_title": "整理今天的对话记忆",
            "focus_context_summary": "当前焦点来自刚接住你这轮话题的事，之所以还在推进，是因为今天这条还剩 2 步没做完。",
            "focus_context_source_kind": "user_topic_goal",
            "focus_context_source_label": "刚接住你这轮话题的事",
            "focus_context_reason_kind": "today_plan_pending",
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

    assert "你当前最在意的焦点目标是「整理今天的对话记忆」" in instructions
    assert "关于这个焦点，此刻更具体的内部依据是" in instructions
    assert "当前焦点来源：刚接住你这轮话题的事。" in instructions
    assert "当前焦点持续原因：今天这条还剩 2 步没做完。" in instructions
    assert "把这个焦点当成与用户当前话题直接相连的线索" in instructions
    assert "刚接住你这轮话题的事" in instructions
    assert "今天这条还剩 2 步没做完" in instructions
