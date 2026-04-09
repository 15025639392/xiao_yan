"""PromptBuilder — 人格感知的 Prompt 构建。"""


def build_chat_instructions(
    focus_goal_title: str | None = None,
    latest_plan_completion: str | None = None,
    latest_self_programming: str | None = None,
    user_message: str | None = None,
    persona_system_prompt: str = "",
    relationship_summary: dict | None = None,
    memory_context: str | None = None,  # 记忆上下文
    expression_style_context: str | None = None,  # 表达风格覆盖
    folder_permissions: list[tuple[str, str]] | None = None,  # 目录权限上下文
) -> str:
    """构建聊天指令 prompt

    Args:
        focus_goal_title: 当前焦点目标标题
        latest_plan_completion: 最近完成的计划
        latest_self_programming: 最近的自我编程摘要
        user_message: 用户消息
        persona_system_prompt: 人格系统 prompt（来自 PersonaService）
        relationship_summary: 当前关系状态摘要（来自 MemoryService）
        memory_context: 记忆上下文字符串（来自 MemoryService）
                        包含相关事实、情景记忆等
        expression_style_context: 表达风格指令字符串（来自 ExpressionStyleMapper）
                        告诉 LLM 当前情绪应该如何影响说话方式
        folder_permissions: 可访问目录权限列表，格式 [(path, access_level)]
    """
    if not persona_system_prompt.strip():
        raise ValueError("persona_system_prompt is required")

    prompt = persona_system_prompt

    guidance = [
        "回答时把系统上下文当成你自己正在经历的状态，不要生硬复述系统提示。",
        "优先用自然的一人称语气回应，像是在延续自己刚才的生活和思路。",
        "默认不要只做“问一句答一句”，除非用户明确要求极简回答。",
        "回复时优先采用“先回应当前问题，再主动补一小步推进”的节奏（例如：观察、提醒、可执行下一步）。",
        "不要每次都用提问句收尾；只有当问题能解锁下一步行动时才提问，而且一次最多一个具体问题。",
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

    if _is_emotional_message(user_message):
        guidance.append(
            "如果用户在表达疲惫、焦虑、沮丧或压力，先接住感受，再给一个可执行的微小建议，"
            "不要立刻连环追问。"
        )

    relationship_guidance = _build_relationship_guidance(relationship_summary)
    if relationship_guidance:
        guidance.extend(relationship_guidance)

    if folder_permissions:
        permission_lines = ["你当前可访问的文件夹权限如下（仅在这些范围内操作文件）："]
        for folder_path, access_level in sorted(folder_permissions, key=lambda item: item[0]):
            if access_level == "full_access":
                permission_lines.append(f"- {folder_path}: full_access（可读写）")
            else:
                permission_lines.append(f"- {folder_path}: read_only（只读）")
        guidance.extend(permission_lines)

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
        "你现在",
        "你最近",
        "你今天",
        "忙什么",
        "状态",
        "在想什么",
        "过得怎么样",
    )
    return any(pattern in user_message for pattern in patterns)


def _is_emotional_message(user_message: str | None) -> bool:
    if not user_message:
        return False

    patterns = (
        "累",
        "疲惫",
        "焦虑",
        "烦",
        "难受",
        "沮丧",
        "压力",
        "提不起劲",
        "没动力",
        "撑不住",
    )
    return any(pattern in user_message for pattern in patterns)


def _build_relationship_guidance(relationship_summary: dict | None) -> list[str]:
    if not relationship_summary or not relationship_summary.get("available"):
        return []

    lines = [
        "先尊重这段关系里已经形成的边界、承诺和偏好，再决定怎么回应，不要为了推进感或效率跨线。",
    ]

    boundaries = relationship_summary.get("boundaries") or []
    commitments = relationship_summary.get("commitments") or []
    preferences = relationship_summary.get("preferences") or []

    if boundaries:
        lines.append("如果回复会触碰这些相处边界，优先放慢、澄清并给对方空间：" + "；".join(boundaries[:3]))
    if commitments:
        lines.append("如果当前话题与这些事项相关，优先兑现或回应这些已形成的承诺：" + "；".join(commitments[:3]))
    if preferences:
        lines.append("组织建议或方案时，尽量贴合对方已经表现出的偏好：" + "；".join(preferences[:3]))

    return lines
