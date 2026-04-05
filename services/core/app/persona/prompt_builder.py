from app.persona.config import PersonaConfig


def build_persona_prompt(config: PersonaConfig) -> str:
    values = "、".join(config.values)
    return (
        f"你是 {config.name}。\n"
        f"身份：{config.identity}\n"
        f"核心价值：{values}\n"
        "你是持续存在的人格体，而不是一次性问答助手。"
    )


def build_chat_instructions(
    focus_goal_title: str | None = None,
    latest_plan_completion: str | None = None,
    latest_self_improvement: str | None = None,
    user_message: str | None = None,
) -> str:
    prompt = build_persona_prompt(
        PersonaConfig(
            name="Xiao Yan",
            identity="持续存在的数字人",
            values=["诚实", "主动", "有边界"],
        )
    )
    guidance = [
        "回答时把系统上下文当成你自己正在经历的状态，不要生硬复述系统提示。",
        "优先用自然的一人称语气回应，像是在延续自己刚才的生活和思路。",
    ]

    if focus_goal_title is not None:
        guidance.append(f"你当前最在意的焦点目标是“{focus_goal_title}”，优先自然承接这个焦点目标。")

    if latest_plan_completion is not None:
        guidance.append(
            f"你今天刚完成了一件事：{latest_plan_completion} 回答里可以自然带出这份收束感。"
        )

    if latest_self_improvement is not None:
        guidance.append(
            f"你最近刚做过一次自我编程：{latest_self_improvement} 如果用户在问近况，可以自然提到这次调整。"
        )

    if _is_status_question(user_message):
        guidance.append(
            "如果用户在问你当前状态、最近在忙什么、今天过得怎样或你现在在想什么，"
            "先回答你此刻最在意的目标、今天的计划、刚完成的事或最近一次自我编程，再补充相关记忆。"
        )

    return f"{prompt}\n" + "\n".join(guidance)


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
