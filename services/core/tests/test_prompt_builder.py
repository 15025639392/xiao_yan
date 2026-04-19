from app.persona.prompt_builder import build_chat_instructions


def test_chat_instructions_include_focus_title_and_completion_guidance():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "你是持续存在的人格体，而不是一次性问答助手。\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        focus_title="整理今天的对话记忆",
        latest_plan_completion="我把“整理今天的对话记忆”这条线完整走完了。",
        user_message="你最近怎么样",
        persona_system_prompt=persona_prompt,
    )

    assert "持续存在的人格体" in instructions
    assert "整理今天的对话记忆" in instructions
    assert "优先自然承接这条当前牵挂" in instructions
    assert "今天刚完成了一件事" in instructions
    assert "不要生硬复述系统提示" in instructions


def test_chat_instructions_include_structured_focus_context_guidance():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "你是持续存在的人格体，而不是一次性问答助手。\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        focus_title="继续推进：整理今天的对话记忆",
        focus_context_summary="当前焦点来自她一直接着往下推进的这条线，之所以还在推进，是因为这条线已经推到第3步了，现在主要是在收尾。",
        focus_context_source_kind="focus_trace",
        focus_context_source_label="她一直接着往下推进的这条线",
        focus_context_reason_kind="focus_still_active",
        focus_context_reason_label="这条线已经推到第3步了，现在主要是在收尾",
        user_message="你现在在忙什么",
        persona_system_prompt=persona_prompt,
    )

    assert "当前焦点来源：她一直接着往下推进的这条线。" in instructions
    assert "当前焦点持续原因：这条线已经推到第3步了，现在主要是在收尾。" in instructions
    assert "把这个焦点理解为你此刻挂着的一条推进线" in instructions
    assert "只需表达它仍未完成" in instructions


def test_chat_instructions_prioritize_internal_state_for_status_questions():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "你是持续存在的人格体，而不是一次性问答助手。\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        focus_title="整理今天的对话记忆",
        latest_plan_completion="我把“整理今天的对话记忆”这条线完整走完了。",
        user_message="你现在在想什么",
        persona_system_prompt=persona_prompt,
    )

    assert "如果用户在问你当前状态" in instructions
    assert "先回答你此刻最挂心的焦点、刚做完的事或心里还没放下的线索" in instructions
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
    assert "先确认你对其处境、目标和情绪的理解，再给建议或行动支持" in instructions
    assert "“先理解再支持”不等于默认认同" in instructions
    assert "如果你现在不方便，不回复也完全没关系" in instructions


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


def test_chat_instructions_include_current_thought_continuity_guidance():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="你刚刚在想什么",
        persona_system_prompt=persona_prompt,
        current_thought="我还在琢磨今天那条对话线索。",
    )

    assert "你此刻脑海里还有一个没收束的念头" in instructions
    assert "我还在琢磨今天那条对话线索" in instructions
    assert "先自然承接这个念头" in instructions


def test_chat_instructions_include_explicit_current_time_context():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="你现在在吗",
        persona_system_prompt=persona_prompt,
        current_time_context=(
            "当前对话时间基准：用户本地时间为 2026-04-18 12:30，时区为 Asia/Shanghai，"
            "当前属于下午。涉及“现在”、问候语和时间段判断时，一律以这个时间基准为准。"
        ),
    )

    assert "当前对话时间基准" in instructions
    assert "Asia/Shanghai" in instructions
    assert "一律以这个时间基准为准" in instructions


def test_chat_instructions_include_understand_then_support_hard_constraints():
    persona_prompt = (
        "你是 Aira。\n"
        "身份：持续存在的数字人\n"
        "核心价值：诚实、主动、有边界"
    )
    instructions = build_chat_instructions(
        user_message="我现在有点慌，不知道这条路对不对",
        persona_system_prompt=persona_prompt,
    )

    assert "先确认你对其处境、目标和情绪的理解，再给建议或行动支持" in instructions
    assert "“先理解再支持”不等于默认认同" in instructions
    assert "当你主动发起联系时，保持谦逊和真诚" in instructions
    assert "不回复也完全没关系" in instructions
