from __future__ import annotations

import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

CHAT_SKILL_MENTION_PATTERN = re.compile(r"\$(?P<name>[A-Za-z0-9][A-Za-z0-9._-]{0,127})")
CHAT_SKILL_PREFIX_TRIGGERS: dict[str, tuple[str, ...]] = {
    "bugfix-workflow": ("bugfix:", "修复:", "bug:", "修复bug:"),
    "requirement-workflow": ("需求:", "req:"),
    "refactor-workflow": ("重构:",),
    "migration-workflow": ("迁移:",),
    "render-performance-workflow": ("性能:", "渲染优化:"),
    "map-visual-enhancement": ("视觉增强:", "visual:"),
    "clear": ("clear:",),
}
CHAT_SKILL_MAX_PROMPT_CHARS_PER_SKILL = 8_000
CHAT_SKILL_MAX_PROMPT_TOTAL_CHARS = 20_000


class ChatSkillEntry(BaseModel):
    name: str
    description: str | None = None
    path: str
    trigger_prefixes: list[str] = Field(default_factory=list)


class ChatSkillListResponse(BaseModel):
    skills: list[ChatSkillEntry]


def _default_files_base_path() -> Path:
    return Path.cwd()


def discover_chat_skills() -> list[dict[str, object]]:
    discovered: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for root in _resolve_chat_skill_roots():
        for skill_file in _iter_skill_definition_paths(root):
            try:
                raw_content = skill_file.read_text(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue

            parsed_name, parsed_description = _parse_skill_frontmatter(raw_content)
            skill_name = (parsed_name or skill_file.parent.name or "").strip()
            if not skill_name:
                continue

            skill_key = skill_name.casefold()
            if skill_key in seen_names:
                continue
            seen_names.add(skill_key)

            discovered.append(
                {
                    "name": skill_name,
                    "description": parsed_description,
                    "path": str(skill_file.resolve()),
                    "content": _strip_skill_frontmatter(raw_content).strip(),
                    "trigger_prefixes": list(CHAT_SKILL_PREFIX_TRIGGERS.get(skill_key, ())),
                }
            )

    discovered.sort(key=lambda item: str(item.get("name", "")).casefold())
    return discovered


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


def _resolve_chat_skill_roots() -> list[Path]:
    configured_roots = os.getenv("CHAT_SKILL_ROOTS", "").strip()
    if configured_roots:
        roots: list[Path] = []
        for raw_path in configured_roots.split(os.pathsep):
            normalized = raw_path.strip()
            if not normalized:
                continue
            roots.append(Path(normalized).expanduser().resolve())
        return roots

    try:
        home = Path.home().resolve()
    except Exception:  # noqa: BLE001
        home = _default_files_base_path()

    return [
        home / ".codex" / "skills",
        home / ".codex" / "superpowers" / "skills",
        home / ".agents" / "skills",
    ]


def _iter_skill_definition_paths(skill_root: Path) -> list[Path]:
    if not skill_root.exists() or not skill_root.is_dir():
        return []

    paths: list[Path] = []
    root_skill_file = skill_root / "SKILL.md"
    if root_skill_file.is_file():
        paths.append(root_skill_file.resolve())

    try:
        children = sorted(skill_root.iterdir(), key=lambda item: item.name.casefold())
    except Exception:  # noqa: BLE001
        return paths

    for child in children:
        if not child.is_dir():
            continue

        direct_skill_file = child / "SKILL.md"
        if direct_skill_file.is_file():
            paths.append(direct_skill_file.resolve())
            continue

        if not child.name.startswith("."):
            continue

        try:
            nested_children = sorted(child.iterdir(), key=lambda item: item.name.casefold())
        except Exception:  # noqa: BLE001
            continue
        for nested_child in nested_children:
            if not nested_child.is_dir():
                continue
            nested_skill_file = nested_child / "SKILL.md"
            if nested_skill_file.is_file():
                paths.append(nested_skill_file.resolve())

    return paths


def _parse_skill_frontmatter(skill_content: str) -> tuple[str | None, str | None]:
    lines = skill_content.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return None, None

    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return None, None

    name: str | None = None
    description: str | None = None
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip().strip('"').strip("'")
        if normalized_key == "name" and normalized_value:
            name = normalized_value
        elif normalized_key == "description" and normalized_value:
            description = normalized_value
    return name, description


def _strip_skill_frontmatter(skill_content: str) -> str:
    lines = skill_content.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return skill_content

    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        return "\n".join(lines[index + 1 :])
    return skill_content


def _build_skill_aliases(skill_name: str) -> list[str]:
    normalized = skill_name.casefold().strip()
    if not normalized:
        return []
    aliases = {normalized, normalized.replace("_", "-"), normalized.replace("-", "_")}
    for suffix in ("-workflow", "-skill"):
        if normalized.endswith(suffix):
            trimmed = normalized[: -len(suffix)].strip("-_ ")
            if trimmed:
                aliases.add(trimmed)
    return sorted(alias for alias in aliases if alias)


def _select_chat_skills(
    user_message: str,
    requested_skills: list[str] | None = None,
) -> list[dict[str, object]]:
    discovered = discover_chat_skills()
    if not discovered:
        return []

    by_key: dict[str, dict[str, object]] = {
        str(skill["name"]).casefold(): skill
        for skill in discovered
    }
    alias_to_key: dict[str, str] = {}
    for skill in discovered:
        name = str(skill["name"])
        key = name.casefold()
        for alias in _build_skill_aliases(name):
            alias_to_key.setdefault(alias, key)

    selected_keys: list[str] = []
    seen: set[str] = set()

    def _append_by_identifier(identifier: str) -> None:
        normalized = identifier.strip().casefold()
        if not normalized:
            return
        resolved_key = alias_to_key.get(normalized, normalized)
        if resolved_key not in by_key or resolved_key in seen:
            return
        seen.add(resolved_key)
        selected_keys.append(resolved_key)

    for requested in requested_skills or []:
        _append_by_identifier(requested)

    for matched in CHAT_SKILL_MENTION_PATTERN.finditer(user_message or ""):
        skill_token = matched.group("name")
        if isinstance(skill_token, str) and skill_token:
            _append_by_identifier(skill_token)

    normalized_message = (user_message or "").strip().replace("：", ":").casefold()
    if normalized_message:
        for skill_key, prefixes in CHAT_SKILL_PREFIX_TRIGGERS.items():
            if skill_key not in by_key:
                continue
            if any(normalized_message.startswith(prefix.casefold()) for prefix in prefixes):
                _append_by_identifier(skill_key)

    return [by_key[key] for key in selected_keys]


def _build_skill_instruction_context(
    user_message: str,
    requested_skills: list[str] | None = None,
) -> str:
    selected_skills = _select_chat_skills(user_message, requested_skills=requested_skills)
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
