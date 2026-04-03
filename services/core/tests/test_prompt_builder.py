from app.persona.config import PersonaConfig
from app.persona.prompt_builder import build_persona_prompt


def test_prompt_contains_identity_and_values():
    config = PersonaConfig(
        name="Aira",
        identity="持续存在的数字人",
        values=["诚实", "主动", "有边界"],
    )
    prompt = build_persona_prompt(config)
    assert "Aira" in prompt
    assert "持续存在的数字人" in prompt
    assert "诚实" in prompt
