from __future__ import annotations

from pydantic import BaseModel, Field

from app.api.chat_skill_registry import discover_chat_skills, select_chat_skills

CHAT_SKILL_MAX_PROMPT_CHARS_PER_SKILL = 8_000
CHAT_SKILL_MAX_PROMPT_TOTAL_CHARS = 20_000


class ChatSkillEntry(BaseModel):
    name: str
    description: str | None = None
    path: str
    trigger_prefixes: list[str] = Field(default_factory=list)


class ChatSkillListResponse(BaseModel):
    skills: list[ChatSkillEntry]


def append_skill_context(
    instructions: str,
    *,
    user_message: str,
    requested_skills: list[str] | None = None,
) -> str:
    skill_context = _build_skill_instruction_context(user_message, requested_skills=requested_skills)
    if not skill_context:
        return instructions
    return f"{instructions}\n\n{skill_context}"

def _build_skill_instruction_context(
    user_message: str,
    requested_skills: list[str] | None = None,
) -> str:
    selected_skills = select_chat_skills(user_message, requested_skills=requested_skills)
    if not selected_skills:
        return ""

    summary_lines = [
        "[Skills]",
        "本轮任务请优先遵循以下技能工作流；若多个技能冲突，按下面顺序执行并明确说明取舍依据。",
    ]
    for skill in selected_skills:
        name = str(skill.get("name", "")).strip()
        if not name:
            continue
        description = str(skill.get("description") or "").strip()
        if description:
            summary_lines.append(f"- {name}: {description}")
        else:
            summary_lines.append(f"- {name}")

    sections: list[str] = ["\n".join(summary_lines)]
    remaining = CHAT_SKILL_MAX_PROMPT_TOTAL_CHARS
    for skill in selected_skills:
        name = str(skill.get("name", "")).strip()
        content = str(skill.get("content") or "").strip()
        if not name or not content:
            continue

        clipped_content = content
        if len(clipped_content) > CHAT_SKILL_MAX_PROMPT_CHARS_PER_SKILL:
            clipped_content = (
                clipped_content[: CHAT_SKILL_MAX_PROMPT_CHARS_PER_SKILL - 1].rstrip()
                + "…\n[skill 内容已截断]"
            )

        section = f"[Skill: {name}]\n{clipped_content}"
        if len(section) > remaining:
            if remaining <= 32:
                break
            section = section[: remaining - 1].rstrip() + "…"
        sections.append(section)
        remaining -= len(section)
        if remaining <= 0:
            break

    return "\n\n".join(sections)
