from app.persona.prompt_builder import build_chat_instructions


def test_chat_instructions_include_focus_goal_and_completion_guidance():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "你是持续存在的人格体，而不是一次性问答助手。\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        focus_goal_title="整理今天的对话记忆",
        latest_plan_completion="我把今天的计划“整理今天的对话记忆”完整走完了。",
        user_message="你最近怎么样",
        persona_system_prompt=persona_prompt,
    )

    assert "持续存在的人格体" in instructions
    assert "整理今天的对话记忆" in instructions
    assert "优先自然承接这个焦点目标" in instructions
    assert "今天刚完成了一件事" in instructions
    assert "不要生硬复述系统提示" in instructions


def test_chat_instructions_prioritize_internal_state_for_status_questions():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "你是持续存在的人格体，而不是一次性问答助手。\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        focus_goal_title="整理今天的对话记忆",
        latest_plan_completion="我把今天的计划“整理今天的对话记忆”完整走完了。",
        latest_self_improvement="我补强了状态展示，并通过了验证。",
        user_message="你现在在想什么",
        persona_system_prompt=persona_prompt,
    )

    assert "如果用户在问你当前状态" in instructions
    assert "最近一次自我编程" in instructions
    assert "先回答你此刻最在意的目标、今天的计划、刚完成的事或最近一次自我编程" in instructions
    assert "再补充相关记忆" in instructions


def test_chat_instructions_require_persona_prompt():
    try:
        build_chat_instructions(user_message="你好")
    except ValueError as exc:
        assert "persona_system_prompt is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")
