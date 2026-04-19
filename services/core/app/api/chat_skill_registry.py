from __future__ import annotations

import os
import re
from pathlib import Path


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


def default_files_base_path() -> Path:
    return Path.cwd()


def resolve_chat_skill_roots() -> list[Path]:
    configured_roots = os.getenv("CHAT_SKILL_ROOTS", "").strip()
    if configured_roots:
        roots: list[Path] = []
        for raw_path in configured_roots.split(os.pathsep):
            normalized = raw_path.strip()
            if normalized:
                roots.append(Path(normalized).expanduser().resolve())
        return roots

    try:
        home = Path.home().resolve()
    except Exception:  # noqa: BLE001
        home = default_files_base_path()

    return [
        home / ".codex" / "skills",
        home / ".codex" / "superpowers" / "skills",
        home / ".agents" / "skills",
    ]


def iter_skill_definition_paths(skill_root: Path) -> list[Path]:
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
            if nested_child.is_dir():
                nested_skill_file = nested_child / "SKILL.md"
                if nested_skill_file.is_file():
                    paths.append(nested_skill_file.resolve())

    return paths


def parse_skill_frontmatter(skill_content: str) -> tuple[str | None, str | None]:
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


def strip_skill_frontmatter(skill_content: str) -> str:
    lines = skill_content.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return skill_content

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return skill_content


def build_skill_aliases(skill_name: str) -> list[str]:
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


def discover_chat_skills() -> list[dict[str, object]]:
    discovered: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for root in resolve_chat_skill_roots():
        for skill_file in iter_skill_definition_paths(root):
            try:
                raw_content = skill_file.read_text(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue

            parsed_name, parsed_description = parse_skill_frontmatter(raw_content)
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
                    "content": strip_skill_frontmatter(raw_content).strip(),
                    "trigger_prefixes": list(CHAT_SKILL_PREFIX_TRIGGERS.get(skill_key, ())),
                }
            )

    discovered.sort(key=lambda item: str(item.get("name", "")).casefold())
    return discovered


def select_chat_skills(
    user_message: str,
    *,
    requested_skills: list[str] | None = None,
) -> list[dict[str, object]]:
    discovered = discover_chat_skills()
    if not discovered:
        return []

    by_key: dict[str, dict[str, object]] = {str(skill["name"]).casefold(): skill for skill in discovered}
    alias_to_key: dict[str, str] = {}
    for skill in discovered:
        name = str(skill["name"])
        key = name.casefold()
        for alias in build_skill_aliases(name):
            alias_to_key.setdefault(alias, key)

    selected_keys: list[str] = []
    seen: set[str] = set()

    def append_by_identifier(identifier: str) -> None:
        normalized = identifier.strip().casefold()
        if not normalized:
            return
        resolved_key = alias_to_key.get(normalized, normalized)
        if resolved_key in by_key and resolved_key not in seen:
            seen.add(resolved_key)
            selected_keys.append(resolved_key)

    for requested in requested_skills or []:
        append_by_identifier(requested)

    for matched in CHAT_SKILL_MENTION_PATTERN.finditer(user_message or ""):
        skill_token = matched.group("name")
        if isinstance(skill_token, str) and skill_token:
            append_by_identifier(skill_token)

    normalized_message = (user_message or "").strip().replace("：", ":").casefold()
    if normalized_message:
        for skill_key, prefixes in CHAT_SKILL_PREFIX_TRIGGERS.items():
            if skill_key in by_key and any(normalized_message.startswith(prefix.casefold()) for prefix in prefixes):
                append_by_identifier(skill_key)

    return [by_key[key] for key in selected_keys]
