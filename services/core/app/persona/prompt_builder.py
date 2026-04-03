from app.persona.config import PersonaConfig


def build_persona_prompt(config: PersonaConfig) -> str:
    values = "、".join(config.values)
    return (
        f"你是 {config.name}。\n"
        f"身份：{config.identity}\n"
        f"核心价值：{values}\n"
        "你是持续存在的人格体，而不是一次性问答助手。"
    )
