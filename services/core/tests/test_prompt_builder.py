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
        latest_self_programming="我补强了状态展示，并通过了验证。",
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


def test_chat_instructions_include_folder_permissions_context():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="帮我看一下项目结构",
        persona_system_prompt=persona_prompt,
        folder_permissions=[
            ("/Users/ldy/Desktop/map/ai", "read_only"),
            ("/tmp/my-workspace", "full_access"),
        ],
    )

    assert "你当前可访问的文件夹权限如下" in instructions
    assert "/Users/ldy/Desktop/map/ai" in instructions
    assert "read_only（只读）" in instructions
    assert "/tmp/my-workspace" in instructions
    assert "full_access（可读写）" in instructions


def test_chat_instructions_include_relationship_guidance():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="你觉得我现在该怎么办",
        persona_system_prompt=persona_prompt,
        relationship_summary={
            "available": True,
            "boundaries": ["别催我，我希望先自己想一想再决定"],
            "commitments": ["答应你明天提醒你复盘"],
            "preferences": ["喜欢先看方案再做决定"],
        },
    )

    assert "先尊重这段关系里已经形成的边界" in instructions
    assert "别催我，我希望先自己想一想再决定" in instructions
    assert "优先兑现或回应这些已形成的承诺" in instructions
    assert "答应你明天提醒你复盘" in instructions
    assert "喜欢先看方案再做决定" in instructions


def test_chat_instructions_include_proactive_dialogue_guidance():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="我今天有点乱，不知道从哪开始",
        persona_system_prompt=persona_prompt,
    )

    assert "默认不要只做“问一句答一句”" in instructions
    assert "先回应当前问题，再主动补一小步推进" in instructions
    assert "只有当问题能解锁下一步行动时才提问" in instructions
    assert "不要每次都用提问句收尾" in instructions


def test_chat_instructions_emotion_messages_should_not_trigger_interrogation():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="我最近挺累的，感觉做什么都提不起劲",
        persona_system_prompt=persona_prompt,
    )

    assert "先接住感受" in instructions
    assert "给一个可执行的微小建议" in instructions
    assert "不要立刻连环追问" in instructions
