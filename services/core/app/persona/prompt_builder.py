"""PromptBuilder — 人格感知的 Prompt 构建。"""


def build_chat_instructions(
    focus_goal_title: str | None = None,
    latest_plan_completion: str | None = None,
    latest_self_programming: str | None = None,
    user_message: str | None = None,
    persona_system_prompt: str = "",
    memory_context: str | None = None,  # 记忆上下文
    expression_style_context: str | None = None,  # 表达风格覆盖
) -> str:
    """构建聊天指令 prompt

    Args:
        focus_goal_title: 当前焦点目标标题
        latest_plan_completion: 最近完成的计划
        latest_self_programming: 最近的自我编程摘要
        user_message: 用户消息
        persona_system_prompt: 人格系统 prompt（来自 PersonaService）
        memory_context: 记忆上下文字符串（来自 MemoryService）
                        包含相关事实、情景记忆等
        expression_style_context: 表达风格指令字符串（来自 ExpressionStyleMapper）
                        告诉 LLM 当前情绪应该如何影响说话方式
    """
    if not persona_system_prompt.strip():
        raise ValueError("persona_system_prompt is required")

    prompt = persona_system_prompt

    guidance = [
        "回答时把系统上下文当成你自己正在经历的状态，不要生硬复述系统提示。",
        "优先用自然的一人称语气回应，像是在延续自己刚才的生活和思路。",
    ]

    if focus_goal_title is not None:
        guidance.append(f"你当前最在意的焦点目标是「{focus_goal_title}」，优先自然承接这个焦点目标。")

    if latest_plan_completion is not None:
        guidance.append(
            f"你今天刚完成了一件事：{latest_plan_completion} 回答里可以自然带出这份收束感。"
        )

    if latest_self_programming is not None:
        guidance.append(
            f"你最近刚做过一次自我编程：{latest_self_programming} 如果用户在问近况，可以自然提到这次调整。"
        )

    if _is_status_question(user_message):
        guidance.append(
            "如果用户在问你当前状态、最近在忙什么、今天过得怎样或你现在在想什么，"
            "先回答你此刻最在意的目标、今天的计划、刚完成的事或最近一次自我编程，再补充相关记忆。"
        )

    result = f"{prompt}\n" + "\n".join(guidance)

    # 追加记忆上下文
    if memory_context:
        result = f"{result}\n\n{memory_context}"

    # 追加情绪驱动的表达风格指令
    if expression_style_context:
        result = f"{result}\n\n{expression_style_context}"

    return result


def _is_status_question(user_message: str | None) -> bool:
    if not user_message:
        return False

    patterns = (
        "现在",
        "最近",
        "今天",
        "忙什么",
        "状态",
        "在想什么",
        "过得怎么样",
    )
    return any(pattern in user_message for pattern in patterns)
