from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from threading import Lock
from time import perf_counter
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
from uuid import uuid4

from app.api.deps import (
    get_chat_gateway,
    get_goal_repository,
    get_memory_repository,
    get_mempalace_adapter,
    get_persona_service,
    get_state_store,
)
from app.config import get_chat_knowledge_extraction_enabled
from app.goals.repository import GoalRepository
from app.capabilities.models import CapabilityDispatchRequest, RiskLevel
from app.capabilities.runtime import dispatch_and_wait, has_recent_capability_executor
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatAttachment,
    ChatMessage,
    ChatReasoningState,
    ChatRequest,
    ChatResumeRequest,
    ChatSubmissionResult,
)
from app.memory.extractor import MemoryExtractor
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.memory.observability import KnowledgeObservabilityTracker
from app.memory.repository import MemoryRepository
from app.memory.search_utils import tokenize_text
from app.mcp import ChatMcpCallRegistry, build_chat_mcp_tool_registry, call_chat_mcp_tool
from app.memory.models import MemoryEvent
from app.persona.expression_mapper import ExpressionStyleMapper
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import FolderAccessLevel, get_runtime_config

CHAT_FILE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a file and return its content. Use absolute paths when possible.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2 * 1024 * 1024},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_directory",
        "description": "List files and directories under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
                "pattern": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_files",
        "description": "Search text in files under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "search_path": {"type": "string"},
                "file_pattern": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Write UTF-8 text to a file path. Requires full_access for granted folders.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "create_dirs": {"type": "boolean"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
]

logger = getLogger(__name__)
RECENT_CONTEXT_WEIGHT = 0.7
LONG_TERM_CONTEXT_WEIGHT = 0.3
LONG_TERM_REFERENCE_LINE_PATTERN = re.compile(
    r"^-\s+(?P<source>\S+)(?:\s+\(相似度\s+(?P<similarity>[0-9]+(?:\.[0-9]+)?)\))?\s*(?P<excerpt>.*)$"
)
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


class FolderPermissionEntry(BaseModel):
    path: str = Field(..., min_length=1)
    access_level: FolderAccessLevel


class FolderPermissionRequest(BaseModel):
    path: str = Field(..., min_length=1)
    access_level: FolderAccessLevel


class FolderPermissionListResponse(BaseModel):
    permissions: list[FolderPermissionEntry]


class ChatSkillEntry(BaseModel):
    name: str
    description: str | None = None
    path: str
    trigger_prefixes: list[str] = Field(default_factory=list)


class ChatSkillListResponse(BaseModel):
    skills: list[ChatSkillEntry]


class ChatMcpServerEntry(BaseModel):
    server_id: str
    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    enabled: bool = True
    timeout_seconds: int = 20


class ChatMcpServerListResponse(BaseModel):
    enabled: bool
    servers: list[ChatMcpServerEntry]


def build_chat_router() -> APIRouter:
    router = APIRouter()
    supported_text_file_extensions = {
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".csv",
        ".log",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
    }
    supported_image_mime_types = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    max_attached_file_bytes = 512 * 1024
    max_attached_image_bytes = 4 * 1024 * 1024
    max_attached_files = 6
    max_attached_images = 4
    max_total_file_context_chars = 16_000
    reasoning_resume_recovery_scan_limit = 800
    reasoning_sessions: dict[str, dict[str, object]] = {}
    reasoning_assistant_map: dict[str, str] = {}
    reasoning_lock = Lock()

    def _normalize_reasoning_session_id(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _coerce_reasoning_state(value: object) -> ChatReasoningState | None:
        if not isinstance(value, dict):
            return None
        try:
            return ChatReasoningState.model_validate(value)
        except Exception:  # noqa: BLE001
            return None

    def _hydrate_reasoning_session_state(reasoning_state: ChatReasoningState) -> None:
        with reasoning_lock:
            reasoning_sessions[reasoning_state.session_id] = reasoning_state.model_dump(mode="json")

    def _resolve_resume_reasoning_session_id(
        request_body: ChatResumeRequest,
        *,
        memory_repository: MemoryRepository,
    ) -> str | None:
        explicit = _normalize_reasoning_session_id(request_body.reasoning_session_id)
        if explicit:
            return explicit

        normalized_assistant_message_id = (request_body.assistant_message_id or "").strip()
        if not normalized_assistant_message_id:
            return None

        with reasoning_lock:
            remembered = reasoning_assistant_map.get(normalized_assistant_message_id)
        if remembered:
            return remembered

        try:
            recent_chat_events = memory_repository.list_recent_chat(limit=reasoning_resume_recovery_scan_limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("resume reasoning recovery scan failed: %s", exc)
            return None

        for event in recent_chat_events:
            if event.role != "assistant":
                continue
            if _normalize_reasoning_session_id(event.session_id) != normalized_assistant_message_id:
                continue
            recovered_reasoning_state = _coerce_reasoning_state(event.reasoning_state)
            recovered_reasoning_session_id = _normalize_reasoning_session_id(event.reasoning_session_id)
            if recovered_reasoning_session_id is None and recovered_reasoning_state is not None:
                recovered_reasoning_session_id = _normalize_reasoning_session_id(recovered_reasoning_state.session_id)
            if recovered_reasoning_session_id is None:
                continue
            if recovered_reasoning_state is not None:
                _hydrate_reasoning_session_state(recovered_reasoning_state)
            _remember_reasoning_session_for_assistant(
                normalized_assistant_message_id,
                recovered_reasoning_session_id,
            )
            return recovered_reasoning_session_id
        return None

    def _remember_reasoning_session_for_assistant(assistant_message_id: str, reasoning_session_id: str) -> None:
        with reasoning_lock:
            reasoning_assistant_map[assistant_message_id] = reasoning_session_id

    def _start_reasoning_session(*, user_message: str, session_id: str | None) -> ChatReasoningState:
        normalized_session_id = _normalize_reasoning_session_id(session_id) or f"reasoning_{uuid4().hex}"
        with reasoning_lock:
            previous = reasoning_sessions.get(normalized_session_id)
            previous_step = int(previous.get("step_index", 0)) if isinstance(previous, dict) else 0
            step_index = max(1, previous_step + 1)
            state = ChatReasoningState(
                session_id=normalized_session_id,
                phase="exploring",
                step_index=step_index,
                summary=(user_message or "").strip()[:72] or "继续推理中",
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            reasoning_sessions[normalized_session_id] = state.model_dump(mode="json")
            return state

    def _update_reasoning_session_after_completion(
        *,
        reasoning_state: ChatReasoningState | None,
        user_message: str,
        output_text: str,
    ) -> ChatReasoningState | None:
        if reasoning_state is None:
            return None

        completion_markers = ("结论", "总结", "已完成", "final", "done")
        is_completed = any(marker in (output_text or "").lower() for marker in completion_markers)
        summarized = _compact_text(output_text or user_message, limit=120) or "继续推理中"
        updated = reasoning_state.model_copy(
            update={
                "phase": "completed" if is_completed else "exploring",
                "summary": summarized,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        with reasoning_lock:
            reasoning_sessions[updated.session_id] = updated.model_dump(mode="json")
        return updated

    def _append_reasoning_instruction(
        instructions: str,
        *,
        reasoning_state: ChatReasoningState | None,
    ) -> str:
        if reasoning_state is None:
            return instructions
        return (
            f"{instructions}\n\n"
            "[Continuous Reasoning]\n"
            f"你正在同一个持续推理会话中（session={reasoning_state.session_id}, step={reasoning_state.step_index}, phase={reasoning_state.phase}）。\n"
            "请延续已有推理，不要重置上下文；输出时先给结论，再给一段简短“阶段摘要”，但不要泄露完整思维链。"
        )

    def _default_files_base_path() -> Path:
        try:
            return Path.home().resolve()
        except Exception:  # noqa: BLE001
            return Path(__file__).resolve().parents[4]

    def _summarize_latest_self_programming(state) -> str | None:
        job = state.self_programming_job
        if job is None:
            return None
        if job.status.value == "applied":
            return f"我补强了 {job.target_area}，并通过了验证。"
        if job.status.value == "failed":
            return f"我尝试补强 {job.target_area}，但还没通过验证。"
        return None

    def _merge_chat_stream_content(current_content: str, delta: str) -> str:
        if not current_content:
            return delta
        if not delta:
            return current_content
        if delta.startswith(current_content):
            return delta
        if current_content.startswith(delta) or delta in current_content:
            return current_content
        max_overlap = min(len(current_content), len(delta))
        for overlap in range(max_overlap, 0, -1):
            if current_content[-overlap:] == delta[:overlap]:
                return f"{current_content}{delta[overlap:]}"
        return f"{current_content}{delta}"

    def _build_resume_instruction(partial_content: str) -> str:
        return (
            "这是一次失败后的继续生成。"
            "你必须紧接着下面这段 assistant 已输出内容继续生成，"
            "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
            f"已输出内容：\n{partial_content}"
        )

    def _resolve_attachment_paths(attachments: list[ChatAttachment], attachment_type: str) -> list[str]:
        resolved_paths: list[str] = []
        seen: set[str] = set()
        for attachment in attachments:
            if attachment.type != attachment_type:
                continue
            path = Path(attachment.path).expanduser()
            if not path.is_absolute():
                raise HTTPException(status_code=400, detail=f"attached {attachment_type} path must be absolute")
            resolved = path.resolve()
            if not resolved.exists():
                raise HTTPException(status_code=404, detail=f"attached {attachment_type} not found")
            if attachment_type == "folder" and not resolved.is_dir():
                raise HTTPException(status_code=400, detail="attached folder path is not a directory")
            if attachment_type in {"file", "image"} and not resolved.is_file():
                raise HTTPException(status_code=400, detail=f"attached {attachment_type} path is not a file")
            normalized = str(resolved)
            if normalized in seen:
                continue
            seen.add(normalized)
            resolved_paths.append(normalized)
        return resolved_paths

    def _supports_image_attachments(provider_id: str, model: str) -> bool:
        normalized_provider = (provider_id or "").strip().lower()
        normalized_model = (model or "").strip().lower()
        if normalized_provider == "nvidia":
            return False
        if normalized_provider == "openai":
            return any(
                normalized_model.startswith(prefix)
                for prefix in ("gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3", "o4")
            )
        if normalized_provider == "deepseek":
            return ("vl" in normalized_model) or ("vision" in normalized_model)
        if normalized_provider == "minimaxi":
            return any(token in normalized_model for token in ("vl", "vision", "omni", "image"))
        return any(token in normalized_model for token in ("vl", "vision", "omni", "image"))

    def _resolve_image_mime_type(path: Path, attachment: ChatAttachment) -> str:
        declared = (attachment.mime_type or "").strip().lower()
        if declared:
            mime_type = declared
        else:
            guessed, _ = mimetypes.guess_type(path.name)
            mime_type = (guessed or "").lower()
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
        if mime_type not in supported_image_mime_types:
            raise HTTPException(status_code=400, detail=f"unsupported image mime type: {mime_type or 'unknown'}")
        return mime_type

    def _read_text_attachment_content(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore[import-not-found]
            except Exception:
                return f"[PDF 附件] {path}\n当前运行环境未安装 pypdf，暂时无法自动提取 PDF 文本。"
            try:
                reader = PdfReader(str(path))
                pages = reader.pages[:8]
                extracted = "\n".join(page.extract_text() or "" for page in pages).strip()
                if not extracted:
                    return f"[PDF 附件] {path}\n未提取到可读文本。"
                return extracted
            except Exception as exception:  # noqa: BLE001
                return f"[PDF 附件] {path}\n解析失败：{exception}"

        if suffix not in supported_text_file_extensions:
            raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix or path.name}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_attached_file_bytes:
                return content[:max_attached_file_bytes]
            return content
        except Exception as exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"failed to read attached file: {exception}") from exception

    def _build_file_attachment_context(file_paths: list[str]) -> str:
        if not file_paths:
            return ""
        if len(file_paths) > max_attached_files:
            raise HTTPException(status_code=400, detail=f"too many file attachments (max {max_attached_files})")

        remaining = max_total_file_context_chars
        sections: list[str] = []
        for file_path in file_paths:
            if remaining <= 0:
                break
            resolved = Path(file_path)
            content = _read_text_attachment_content(resolved).strip()
            if not content:
                continue
            clipped = content[:remaining]
            remaining -= len(clipped)
            sections.append(f"[附件文件] {file_path}\n{clipped}")
        return "\n\n".join(sections)

    def _build_image_content_parts(
        *,
        attachments: list[ChatAttachment],
        image_paths: list[str],
        provider_id: str,
        model: str,
        wire_api: str,
    ) -> list[dict]:
        if not image_paths:
            return []
        if len(image_paths) > max_attached_images:
            raise HTTPException(status_code=400, detail=f"too many image attachments (max {max_attached_images})")
        if not _supports_image_attachments(provider_id, model):
            raise HTTPException(
                status_code=400,
                detail=f"current model does not support image attachments: {provider_id}/{model}",
            )

        by_path: dict[str, ChatAttachment] = {}
        for attachment in attachments:
            if attachment.type != "image":
                continue
            resolved = str(Path(attachment.path).expanduser().resolve())
            by_path.setdefault(resolved, attachment)

        parts: list[dict] = []
        for image_path in image_paths:
            resolved = Path(image_path)
            attachment = by_path.get(image_path, ChatAttachment(type="image", path=image_path))
            mime_type = _resolve_image_mime_type(resolved, attachment)
            image_size = resolved.stat().st_size
            if image_size > max_attached_image_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"image too large (> {max_attached_image_bytes} bytes): {image_path}",
                )
            raw = resolved.read_bytes()
            data_url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"

            if wire_api == "responses":
                parts.append({"type": "input_image", "image_url": data_url})
            else:
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        return parts

    def _append_attachment_context(
        instructions: str,
        *,
        folder_paths: list[str],
        file_paths: list[str],
        image_paths: list[str],
    ) -> str:
        lines: list[str] = []
        if folder_paths:
            lines.append("本轮用户附加了这些文件夹上下文（优先在这些目录中查找，不要臆造不存在的文件内容）：")
            lines.extend(f"- {folder_path}" for folder_path in folder_paths)
        if file_paths:
            lines.append("本轮用户附加了这些文件（必要时可继续用工具读取原文）：")
            lines.extend(f"- {file_path}" for file_path in file_paths)
        if image_paths:
            lines.append("本轮用户附加了这些图片（请结合图片内容与文本一起回答）：")
            lines.extend(f"- {image_path}" for image_path in image_paths)
        if not lines:
            return instructions
        return f"{instructions}\n\n" + "\n".join(lines)

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

    def _discover_chat_skills() -> list[dict[str, object]]:
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

    def _select_chat_skills(user_message: str, requested_skills: list[str] | None = None) -> list[dict[str, object]]:
        discovered = _discover_chat_skills()
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

    def _append_skill_context(
        instructions: str,
        *,
        user_message: str,
        requested_skills: list[str] | None = None,
    ) -> str:
        skill_context = _build_skill_instruction_context(user_message, requested_skills=requested_skills)
        if not skill_context:
            return instructions
        return f"{instructions}\n\n{skill_context}"

    def _build_attachment_permission_paths(
        *,
        folder_paths: list[str],
        file_paths: list[str],
        image_paths: list[str],
    ) -> list[str]:
        granted: set[str] = set(folder_paths)
        for file_path in file_paths:
            granted.add(str(Path(file_path).parent))
        for image_path in image_paths:
            granted.add(str(Path(image_path).parent))
        return sorted(granted)

    def _apply_user_content_to_messages(
        messages: list[ChatMessage],
        *,
        user_content: str | list[dict],
    ) -> list[ChatMessage]:
        patched = [message.model_copy(deep=True) for message in messages]
        for index in range(len(patched) - 1, -1, -1):
            if patched[index].role == "user":
                patched[index] = ChatMessage(role="user", content=user_content)
                return patched
        patched.append(ChatMessage(role="user", content=user_content))
        return patched

    def _compact_text(text: str | None, *, limit: int) -> str:
        if not text:
            return ""
        compacted = " ".join(text.strip().split())
        if len(compacted) <= limit:
            return compacted
        return f"{compacted[: limit - 1].rstrip()}…"

    def _build_post_chat_thought(user_message: str, assistant_response: str) -> str:
        topic = _compact_text(user_message, limit=28) or "刚才这段对话"
        first_line = next((line for line in assistant_response.splitlines() if line.strip()), assistant_response)
        assistant_snippet = _compact_text(first_line, limit=42)
        if assistant_snippet:
            return f"我刚顺着“{topic}”回应了你，脑子里还停着这句：{assistant_snippet}"
        return f"我刚顺着“{topic}”回应了你，接下来想把它再往前推一小步。"

    def _mirror_exchange_to_memory_repository(
        *,
        memory_repository: MemoryRepository,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str,
        reasoning_session_id: str | None = None,
        reasoning_state: ChatReasoningState | None = None,
    ) -> None:
        user_text = (user_message or "").strip()
        assistant_text = (assistant_response or "").strip()
        if not user_text or not assistant_text:
            return
        normalized_reasoning_session_id = _normalize_reasoning_session_id(reasoning_session_id)
        reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

        memory_repository.save_event(
            MemoryEvent(
                kind="chat",
                content=user_text,
                role="user",
            )
        )
        memory_repository.save_event(
            MemoryEvent(
                kind="chat",
                content=assistant_text,
                role="assistant",
                session_id=assistant_session_id,
                reasoning_session_id=normalized_reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        )

    def _extract_structured_knowledge_events(
        *,
        memory_repository: MemoryRepository,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str,
        personality,
    ) -> int:
        user_text = (user_message or "").strip()
        assistant_text = (assistant_response or "").strip()
        if not user_text or not assistant_text:
            return 0

        extractor = MemoryExtractor(personality=personality)
        events = extractor.extract_from_dialogue(
            [
                ChatMessage(role="user", content=user_text),
                ChatMessage(role="assistant", content=assistant_text),
            ],
            {
                "source_ref": f"chat://{assistant_session_id}",
                "version_tag": "v1",
                "topic": _compact_text(user_text, limit=40),
            },
        )
        for event in events:
            memory_repository.save_event(event)
        return len(events)

    def _should_fallback_to_stream_without_tools(exception: Exception) -> bool:
        if not isinstance(exception, httpx.HTTPStatusError):
            return False
        status_code = exception.response.status_code if exception.response is not None else None
        return status_code in {400, 404, 405, 415, 422, 501}

    def _normalize_folder_path(raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise HTTPException(status_code=400, detail="folder path must be absolute")
        return path.resolve()

    def _build_folder_permission_response() -> FolderPermissionListResponse:
        config = get_runtime_config()
        entries = [
            FolderPermissionEntry(path=path, access_level=access_level)
            for path, access_level in config.list_folder_permissions()
        ]
        return FolderPermissionListResponse(permissions=entries)

    def _file_policy_args() -> dict:
        config = get_runtime_config()
        return {"file_policy": config.get_capability_file_policy()}

    def _get_observability_tracker(request: Request) -> KnowledgeObservabilityTracker | None:
        tracker = getattr(request.app.state, "knowledge_observability_tracker", None)
        if isinstance(tracker, KnowledgeObservabilityTracker):
            return tracker
        return None

    def _record_retrieval_observability(
        *,
        tracker: KnowledgeObservabilityTracker | None,
        latency_ms: float,
        references: list[dict[str, str | float | None]],
        failed: bool,
    ) -> None:
        if tracker is None:
            return
        similarity_scores: list[float] = []
        for reference in references:
            similarity = reference.get("similarity")
            if isinstance(similarity, (int, float)):
                similarity_scores.append(float(similarity))
        tracker.record_retrieval(
            latency_ms=latency_ms,
            hit_count=len(references),
            similarity_scores=similarity_scores,
            failed=failed,
        )

    def _run_chat_submission(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
        suppress_started_event: bool = False,
        knowledge_references: list[dict[str, str | float | None]] | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: ChatReasoningState | None = None,
    ) -> tuple[ChatSubmissionResult, str]:
        response_id: str | None = None
        output_text = initial_output_text
        started = False
        hub = getattr(request.app.state, "realtime_hub", None)
        reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

        try:
            for event in gateway.stream_response(chat_messages, instructions=instructions):
                event_type = event["type"]
                if event_type == "response_started":
                    response_id = event.get("response_id") or response_id
                    if hub is not None and not started and not suppress_started_event:
                        hub.publish_chat_started(
                            assistant_message_id,
                            response_id=response_id,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                        started = True
                    continue

                if event_type == "text_delta":
                    if hub is not None and not started and not suppress_started_event:
                        hub.publish_chat_started(
                            assistant_message_id,
                            response_id=response_id,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                        started = True

                    delta = event.get("delta") or ""
                    if not delta:
                        continue

                    output_text = _merge_chat_stream_content(output_text, delta)
                    if hub is not None:
                        hub.publish_chat_delta(
                            assistant_message_id,
                            delta,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                    continue

                if event_type == "response_completed":
                    response_id = event.get("response_id") or response_id
                    completed_output_text = event.get("output_text") or ""
                    if completed_output_text and completed_output_text not in output_text:
                        output_text = completed_output_text
                    continue

                if event_type == "response_failed":
                    error_message = event.get("error") or "streaming failed"
                    if hub is not None:
                        hub.publish_chat_failed(
                            assistant_message_id,
                            error_message,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                    raise HTTPException(status_code=502, detail=error_message)
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            try:
                if exception.response is not None:
                    detail = exception.response.text or detail
            except Exception:  # noqa: BLE001
                pass
            if hub is not None:
                hub.publish_chat_failed(
                    assistant_message_id,
                    detail,
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=detail) from exception
        except HTTPException:
            raise
        except Exception as exception:
            if hub is not None:
                hub.publish_chat_failed(
                    assistant_message_id,
                    str(exception),
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=str(exception)) from exception

        if hub is not None and not started and not suppress_started_event:
            hub.publish_chat_started(
                assistant_message_id,
                response_id=response_id,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        if hub is not None:
            hub.publish_chat_completed(
                assistant_message_id,
                response_id,
                output_text,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )

        return (
            ChatSubmissionResult(
                response_id=response_id,
                assistant_message_id=assistant_message_id,
            ),
            output_text,
        )

    def _build_chat_file_tools():
        from app.tools.file_tools import FileTools

        default_base_path = _default_files_base_path()
        config = get_runtime_config()
        granted_folders = {path: access_level for path, access_level in config.list_folder_permissions()}
        return FileTools(
            allowed_base_path=default_base_path,
            folder_permissions=granted_folders,
        )

    def _build_chat_mcp_server_response() -> ChatMcpServerListResponse:
        config = get_runtime_config()
        servers = [
            ChatMcpServerEntry(
                server_id=str(item.get("server_id", "")),
                command=str(item.get("command", "")),
                args=[str(arg) for arg in (item.get("args") or []) if isinstance(arg, str)],
                cwd=str(item.get("cwd")) if item.get("cwd") is not None else None,
                enabled=bool(item.get("enabled", True)),
                timeout_seconds=int(item.get("timeout_seconds", 20)),
            )
            for item in config.list_chat_mcp_servers()
            if str(item.get("server_id", "")).strip() and str(item.get("command", "")).strip()
        ]
        return ChatMcpServerListResponse(enabled=config.chat_mcp_enabled, servers=servers)

    def _build_chat_mcp_registry(requested_server_ids: list[str]) -> ChatMcpCallRegistry:
        config = get_runtime_config()
        return build_chat_mcp_tool_registry(
            mcp_enabled=config.chat_mcp_enabled,
            configured_servers=config.list_chat_mcp_servers(),
            selected_server_ids=requested_server_ids,
        )

    def _resolve_mempalace_chat_context(
        *,
        user_message: str,
        mempalace_adapter: MemPalaceAdapter,
        memory_repository: MemoryRepository,
        context_limit: int,
    ) -> tuple[list[ChatMessage], str, bool, bool]:
        recent_turn_limit, long_term_hits = _split_context_budget(context_limit)
        memory_context = ""
        search_failed = False
        retrieval_attempted = False
        should_search_cross_room = True
        supports_cross_room_probe = hasattr(mempalace_adapter, "has_cross_room_long_term_sources")
        if supports_cross_room_probe:
            try:
                should_search_cross_room = bool(mempalace_adapter.has_cross_room_long_term_sources())
            except Exception as exc:  # noqa: BLE001
                logger.warning("MemPalace has_cross_room_long_term_sources raised unexpectedly: %s", exc)
                should_search_cross_room = True
        try:
            if should_search_cross_room:
                retrieval_attempted = True
                # Long-term retrieval should avoid the live chat room to prevent
                # duplicating content that is already injected via recent messages.
                memory_context = mempalace_adapter.search_context(
                    user_message,
                    exclude_current_room=True,
                    max_hits=long_term_hits,
                    retrieval_weight=LONG_TERM_CONTEXT_WEIGHT,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace search_context raised unexpectedly: %s", exc)
            memory_context = ""
            search_failed = True

        try:
            chat_messages = mempalace_adapter.build_chat_messages(
                user_message,
                limit=recent_turn_limit,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace build_chat_messages raised unexpectedly: %s", exc)
            chat_messages = [ChatMessage(role="user", content=user_message)]

        if not chat_messages:
            chat_messages = [ChatMessage(role="user", content=user_message)]

        approved_knowledge_context = _build_approved_knowledge_context(
            memory_repository=memory_repository,
            user_message=user_message,
            max_hits=long_term_hits,
        )
        if approved_knowledge_context:
            if memory_context:
                memory_context = f"{memory_context}\n{approved_knowledge_context}"
            else:
                memory_context = approved_knowledge_context

        return chat_messages, memory_context, search_failed, retrieval_attempted

    def _build_approved_knowledge_context(
        *,
        memory_repository: MemoryRepository,
        user_message: str,
        max_hits: int,
    ) -> str:
        safe_hits = max(1, int(max_hits))
        try:
            events = memory_repository.list_recent(
                limit=max(safe_hits * 5, 20),
                status="active",
                namespace="knowledge",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to load approved knowledge events: %s", exc)
            return ""

        approved_events = [event for event in events if getattr(event, "review_status", "approved") == "approved"]
        if not approved_events:
            return ""

        ranked_events = _rank_approved_knowledge_events(
            events=approved_events,
            user_message=user_message,
            max_hits=safe_hits,
        )

        lines = ["【结构化知识（已审核）】"]
        for event in ranked_events:
            excerpt = _compact_text(event.content or "", limit=180)
            if not excerpt:
                continue
            source = _compact_text((event.source_ref or "knowledge/approved"), limit=120).replace(" ", "_")
            lines.append(f"- {source} {excerpt}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _rank_approved_knowledge_events(
        *,
        events: list[MemoryEvent],
        user_message: str,
        max_hits: int,
    ) -> list[MemoryEvent]:
        safe_hits = max(1, int(max_hits))
        query_tokens = tokenize_text(user_message or "")
        normalized_query = (user_message or "").strip().lower()
        now_utc = datetime.now(timezone.utc)

        scored: list[tuple[float, float, float, float, MemoryEvent]] = []
        for event in events:
            relevance_score = _score_approved_knowledge_relevance(
                event=event,
                query_tokens=query_tokens,
                normalized_query=normalized_query,
            )
            freshness_score = _score_approved_knowledge_freshness(event=event, now_utc=now_utc)
            combined_score = _merge_approved_knowledge_scores(
                relevance_score=relevance_score,
                freshness_score=freshness_score,
                has_query=bool(query_tokens),
            )
            scored.append((combined_score, relevance_score, freshness_score, _event_timestamp(event), event))

        scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
        return [item[4] for item in scored[:safe_hits]]

    def _score_approved_knowledge_relevance(
        *,
        event: MemoryEvent,
        query_tokens: set[str],
        normalized_query: str,
    ) -> float:
        if not query_tokens:
            return 0.0

        event_index_text = " ".join(
            part
            for part in (
                event.content or "",
                " ".join(event.knowledge_tags),
                event.knowledge_type or "",
                event.source_ref or "",
            )
            if part
        )
        event_tokens = tokenize_text(event_index_text)
        overlap = len(query_tokens & event_tokens)
        token_coverage = overlap / max(1, len(query_tokens))
        phrase_bonus = 0.0
        if normalized_query and normalized_query in (event.content or "").lower():
            phrase_bonus = 0.25
        return min(1.0, token_coverage + phrase_bonus)

    def _score_approved_knowledge_freshness(*, event: MemoryEvent, now_utc: datetime) -> float:
        created_at = event.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (now_utc - created_at).total_seconds())
        freshness_half_life_seconds = 14 * 24 * 60 * 60
        return float(0.5 ** (age_seconds / freshness_half_life_seconds))

    def _merge_approved_knowledge_scores(*, relevance_score: float, freshness_score: float, has_query: bool) -> float:
        if not has_query:
            return freshness_score
        return (relevance_score * 0.75) + (freshness_score * 0.25)

    def _event_timestamp(event: MemoryEvent) -> float:
        created_at = event.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at.timestamp()

    def _split_context_budget(context_limit: int) -> tuple[int, int]:
        total = max(1, int(context_limit))
        long_term_hits = max(1, int(round(total * LONG_TERM_CONTEXT_WEIGHT)))
        recent_turn_limit = max(1, int(round(total * RECENT_CONTEXT_WEIGHT)))
        return recent_turn_limit, long_term_hits

    def _extract_knowledge_references(memory_context: str) -> list[dict[str, str | float | None]]:
        if not memory_context:
            return []

        references: list[dict[str, str | float | None]] = []
        for line in memory_context.splitlines():
            match = LONG_TERM_REFERENCE_LINE_PATTERN.match(line.strip())
            if match is None:
                continue

            source = (match.group("source") or "").strip()
            excerpt = (match.group("excerpt") or "").strip()
            if not source or not excerpt:
                continue

            wing = source
            room = ""
            if "/" in source:
                wing, room = source.split("/", 1)

            similarity: float | None = None
            similarity_text = match.group("similarity")
            if similarity_text:
                try:
                    similarity = round(float(similarity_text), 4)
                except ValueError:
                    similarity = None

            references.append(
                {
                    "source": source,
                    "wing": wing,
                    "room": room,
                    "similarity": similarity,
                    "excerpt": excerpt,
                }
            )

        return references

    def _execute_tool_call(
        file_tools,
        tool_name: str,
        arguments: dict,
        *,
        mcp_registry: ChatMcpCallRegistry | None = None,
    ) -> str:
        def _try_dispatch(tool: str, args: dict) -> str | None:
            if not has_recent_capability_executor("desktop", max_age_seconds=10):
                return None

            capability_map = {
                "read_file": ("fs.read", RiskLevel.SAFE, False),
                "list_directory": ("fs.list", RiskLevel.SAFE, False),
                "search_files": ("fs.search", RiskLevel.RESTRICTED, False),
                "write_file": ("fs.write", RiskLevel.RESTRICTED, False),
            }
            mapping = capability_map.get(tool)
            if mapping is None:
                return None

            capability, risk_level, requires_approval = mapping
            result = dispatch_and_wait(
                CapabilityDispatchRequest(
                    capability=capability,
                    args={**args, **_file_policy_args()},
                    risk_level=risk_level,
                    requires_approval=requires_approval,
                ),
                timeout_seconds=0.8,
                poll_interval_seconds=0.05,
            )

            # timeout: fallback to existing core-local execution
            if result is None:
                return None

            if not result.ok:
                if result.error_code == "not_supported":
                    return None
                return json.dumps(
                    {
                        "error": result.error_message or result.error_code or "capability execution failed",
                        "capability_request_id": result.request_id,
                    },
                    ensure_ascii=False,
                )

            output = result.output if isinstance(result.output, dict) else {}
            if tool == "read_file":
                content = output.get("content")
                if not isinstance(content, str):
                    return json.dumps(
                        {"error": "invalid capability output for read_file", "capability_request_id": result.request_id},
                        ensure_ascii=False,
                    )
                path_value = output.get("path", str(args.get("path", "")))
                if not isinstance(path_value, str):
                    path_value = str(args.get("path", ""))
                size_bytes = output.get("size_bytes")
                if not isinstance(size_bytes, int):
                    size_bytes = len(content.encode("utf-8"))
                line_count = output.get("line_count")
                if not isinstance(line_count, int):
                    line_count = content.count("\n") + 1 if content else 1
                payload = {
                    "path": path_value,
                    "content": content,
                    "size_bytes": size_bytes,
                    "encoding": "utf-8",
                    "line_count": line_count,
                    "truncated": bool(output.get("truncated", False)),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            if tool == "list_directory":
                path_value = output.get("path", str(args.get("path", ".")))
                if not isinstance(path_value, str):
                    path_value = str(args.get("path", "."))
                raw_entries = output.get("entries")
                entries = []
                if isinstance(raw_entries, list):
                    for item in raw_entries:
                        if isinstance(item, str):
                            entries.append(
                                {
                                    "name": item,
                                    "path": item,
                                    "type": "other",
                                    "size_bytes": 0,
                                    "modified_at": None,
                                }
                            )
                        elif isinstance(item, dict):
                            entries.append(item)
                payload = {
                    "path": path_value,
                    "entries": entries,
                    "total_files": 0,
                    "total_dirs": 0,
                    "truncated": bool(output.get("truncated", False)),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            if tool == "write_file":
                path_value = output.get("path", str(args.get("path", "")))
                if not isinstance(path_value, str):
                    path_value = str(args.get("path", ""))
                payload = {
                    "path": path_value,
                    "success": True,
                    "bytes_written": output.get("bytes_written"),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            if tool == "search_files":
                payload = {
                    "query": output.get("query", str(args.get("query", ""))),
                    "matches": output.get("matches", []),
                    "total_matches": output.get("total_matches", 0),
                    "search_duration_seconds": output.get("search_duration_seconds", 0),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            return None

        try:
            if tool_name == "read_file":
                path = str(arguments.get("path", ""))
                max_bytes = int(arguments.get("max_bytes", 512 * 1024))
                dispatched = _try_dispatch("read_file", {"path": path, "max_bytes": max_bytes})
                if dispatched is not None:
                    return dispatched
                result = file_tools.read_file(path, max_bytes=max_bytes)
                payload = result.to_dict()
                payload["content"] = result.content
                return json.dumps(payload, ensure_ascii=False)

            if tool_name == "list_directory":
                path = str(arguments.get("path", "."))
                recursive = bool(arguments.get("recursive", False))
                pattern = arguments.get("pattern")
                pattern_value = None if pattern is None else str(pattern)
                dispatched = _try_dispatch(
                    "list_directory",
                    {"path": path, "recursive": recursive, "pattern": pattern_value},
                )
                if dispatched is not None:
                    return dispatched
                result = file_tools.list_directory(path, recursive=recursive, pattern=pattern_value)
                return json.dumps(result.to_dict(), ensure_ascii=False)

            if tool_name == "search_files":
                query = str(arguments.get("query", ""))
                if not query:
                    return json.dumps({"error": "query is required"}, ensure_ascii=False)
                search_path = str(arguments.get("search_path", "."))
                file_pattern = str(arguments.get("file_pattern", "*.py"))
                max_results = int(arguments.get("max_results", 20))
                dispatched = _try_dispatch(
                    "search_files",
                    {
                        "query": query,
                        "search_path": search_path,
                        "file_pattern": file_pattern,
                        "max_results": max_results,
                    },
                )
                if dispatched is not None:
                    return dispatched
                result = file_tools.search_content(
                    query,
                    search_path,
                    file_pattern=file_pattern,
                    max_results=max_results,
                )
                return json.dumps(result.to_dict(), ensure_ascii=False)

            if tool_name == "write_file":
                path = str(arguments.get("path", ""))
                content = str(arguments.get("content", ""))
                create_dirs = bool(arguments.get("create_dirs", True))
                dispatched = _try_dispatch(
                    "write_file",
                    {"path": path, "content": content, "create_dirs": create_dirs},
                )
                if dispatched is not None:
                    return dispatched
                result = file_tools.write_file(path, content, create_dirs=create_dirs)
                return json.dumps(result.to_dict(), ensure_ascii=False)

            if mcp_registry is not None:
                mcp_output = call_chat_mcp_tool(
                    mcp_registry,
                    tool_name=tool_name,
                    arguments=arguments,
                )
                if mcp_output is not None:
                    return mcp_output

            return json.dumps({"error": f"unknown tool: {tool_name}"}, ensure_ascii=False)
        except Exception as exception:  # noqa: BLE001
            return json.dumps({"error": str(exception)}, ensure_ascii=False)

    def _extract_function_calls(response_payload: dict) -> list[tuple[str, str, dict]]:
        calls: list[tuple[str, str, dict]] = []
        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            return calls

        for item in output_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue

            call_id = item.get("call_id")
            tool_name = item.get("name")
            raw_arguments = item.get("arguments", "{}")
            if not isinstance(call_id, str) or not isinstance(tool_name, str):
                continue

            arguments: dict = {}
            if isinstance(raw_arguments, str):
                try:
                    parsed = json.loads(raw_arguments)
                    if isinstance(parsed, dict):
                        arguments = parsed
                except json.JSONDecodeError:
                    arguments = {}
            elif isinstance(raw_arguments, dict):
                arguments = raw_arguments

            calls.append((call_id, tool_name, arguments))

        return calls

    def _build_function_call_signature(function_calls: list[tuple[str, str, dict]]) -> str:
        normalized: list[dict[str, str]] = []
        for _, tool_name, arguments in function_calls:
            try:
                arguments_key = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
            except Exception:  # noqa: BLE001
                arguments_key = str(arguments)
            normalized.append({"tool": tool_name, "arguments": arguments_key})
        try:
            return json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        except Exception:  # noqa: BLE001
            return str(normalized)

    def _extract_output_text(response_payload: dict) -> str:
        if isinstance(response_payload.get("output_text"), str):
            return response_payload["output_text"]

        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            return ""

        for item in output_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            for content_item in item.get("content", []):
                if not isinstance(content_item, dict):
                    continue
                content_type = content_item.get("type")
                if content_type not in {"output_text", "text"}:
                    continue
                text = content_item.get("text")
                if isinstance(text, str) and text:
                    return text
        return ""

    def _run_chat_submission_with_tools(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
        knowledge_references: list[dict[str, str | float | None]] | None = None,
        extra_tools: list[dict[str, object]] | None = None,
        mcp_registry: ChatMcpCallRegistry | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: ChatReasoningState | None = None,
    ) -> tuple[ChatSubmissionResult, str]:
        create_with_tools = getattr(gateway, "create_response_with_tools", None)
        if not callable(create_with_tools):
            return _run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                initial_output_text=initial_output_text,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )

        hub = getattr(request.app.state, "realtime_hub", None)
        started = False
        response_id: str | None = None
        reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

        file_tools = _build_chat_file_tools()
        tool_definitions = [*CHAT_FILE_TOOL_DEFINITIONS, *(extra_tools or [])]
        accumulated_input: list[dict] = [message.model_dump() for message in chat_messages]
        max_tool_rounds = 8
        tool_repeat_streak_limit = 3
        last_call_signature: str | None = None
        same_call_signature_streak = 0
        # Lightweight diagnostics: helps identify "content too large" cases in provider errors.
        payload_hint = f"messages={len(chat_messages)}, instructions_chars={len(instructions or '')}"

        def _fallback_without_tools(reason: str) -> tuple[ChatSubmissionResult, str]:
            fallback_instructions = (
                f"{instructions}\n\n"
                "[Tool fallback]\n"
                f"工具调用出现循环/超限（{reason}）。"
                "请不要再调用任何工具，直接基于已有上下文回答；"
                "如信息不足请明确说明不足点。"
            )
            return _run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=fallback_instructions,
                assistant_message_id=assistant_message_id,
                initial_output_text=initial_output_text,
                suppress_started_event=started,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )

        try:
            for _ in range(max_tool_rounds):
                try:
                    response_payload = create_with_tools(
                        accumulated_input,
                        instructions=instructions,
                        tools=tool_definitions,
                    )
                except Exception as exception:  # noqa: BLE001
                    # Some providers reject tool payloads; degrade to plain streaming instead of hard failing.
                    if (
                        not started
                        and len(accumulated_input) == len(chat_messages)
                        and _should_fallback_to_stream_without_tools(exception)
                    ):
                        return _run_chat_submission(
                            request=request,
                            gateway=gateway,
                            chat_messages=chat_messages,
                            instructions=instructions,
                            assistant_message_id=assistant_message_id,
                            initial_output_text=initial_output_text,
                            knowledge_references=knowledge_references,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_state,
                        )
                    raise
                if not isinstance(response_payload, dict):
                    raise HTTPException(status_code=502, detail="invalid gateway response payload")

                current_response_id = response_payload.get("id")
                if isinstance(current_response_id, str):
                    response_id = current_response_id

                function_calls = _extract_function_calls(response_payload)
                if not function_calls:
                    output_text = _extract_output_text(response_payload)
                    if initial_output_text:
                        output_text = _merge_chat_stream_content(initial_output_text, output_text)

                    # Some providers may return an empty non-stream tool response even when normal
                    # streaming works. On the first turn, degrade to plain streaming to avoid
                    # returning an empty assistant reply.
                    if (
                        not output_text
                        and not started
                        and len(accumulated_input) == len(chat_messages)
                    ):
                        return _run_chat_submission(
                            request=request,
                            gateway=gateway,
                            chat_messages=chat_messages,
                            instructions=instructions,
                            assistant_message_id=assistant_message_id,
                            initial_output_text=initial_output_text,
                            knowledge_references=knowledge_references,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_state,
                        )

                    if not output_text:
                        raise HTTPException(status_code=502, detail="empty gateway response payload")

                    if hub is not None and not started:
                        hub.publish_chat_started(
                            assistant_message_id,
                            response_id=response_id,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                        started = True

                    if hub is not None and output_text:
                        hub.publish_chat_delta(
                            assistant_message_id,
                            output_text,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                    if hub is not None:
                        hub.publish_chat_completed(
                            assistant_message_id,
                            response_id,
                            output_text,
                            knowledge_references=knowledge_references,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )

                    return (
                        ChatSubmissionResult(
                            response_id=response_id,
                            assistant_message_id=assistant_message_id,
                        ),
                        output_text,
                    )

                if hub is not None and not started:
                    hub.publish_chat_started(
                        assistant_message_id,
                        response_id=response_id,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                    started = True

                call_signature = _build_function_call_signature(function_calls)
                if call_signature == last_call_signature:
                    same_call_signature_streak += 1
                else:
                    same_call_signature_streak = 1
                    last_call_signature = call_signature
                if same_call_signature_streak >= tool_repeat_streak_limit:
                    return _fallback_without_tools("repeated_tool_calls")

                tool_outputs: list[dict[str, str]] = []
                for call_id, tool_name, arguments in function_calls:
                    tool_output = _execute_tool_call(
                        file_tools,
                        tool_name,
                        arguments,
                        mcp_registry=mcp_registry,
                    )
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": tool_output,
                        }
                    )

                response_outputs = response_payload.get("output", [])
                if isinstance(response_outputs, list):
                    for output_item in response_outputs:
                        if isinstance(output_item, dict):
                            accumulated_input.append(output_item)

                accumulated_input.extend(tool_outputs)

            return _fallback_without_tools("tool_call_recursion_limit_exceeded")
        except HTTPException:
            if hub is not None and started:
                hub.publish_chat_failed(
                    assistant_message_id,
                    "tool execution failed",
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            try:
                if exception.response is not None:
                    detail = exception.response.text or detail
            except Exception:  # noqa: BLE001
                pass
            if hub is not None and started:
                hub.publish_chat_failed(
                    assistant_message_id,
                    f"{payload_hint}; {detail}",
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=f"{payload_hint}; {detail}") from exception
        except Exception as exception:  # noqa: BLE001
            if hub is not None and started:
                hub.publish_chat_failed(
                    assistant_message_id,
                    str(exception),
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=str(exception)) from exception

    @router.get("/chat/folder-permissions")
    def get_folder_permissions() -> FolderPermissionListResponse:
        return _build_folder_permission_response()

    @router.get("/chat/skills")
    def get_chat_skills() -> ChatSkillListResponse:
        return ChatSkillListResponse(
            skills=[
                ChatSkillEntry(
                    name=str(skill.get("name", "")),
                    description=(
                        str(skill.get("description"))
                        if skill.get("description") is not None
                        else None
                    ),
                    path=str(skill.get("path", "")),
                    trigger_prefixes=[
                        str(prefix)
                        for prefix in (skill.get("trigger_prefixes") or [])
                        if isinstance(prefix, str)
                    ],
                )
                for skill in _discover_chat_skills()
                if str(skill.get("name", "")).strip() and str(skill.get("path", "")).strip()
            ]
        )

    @router.get("/chat/mcp/servers")
    def get_chat_mcp_servers() -> ChatMcpServerListResponse:
        return _build_chat_mcp_server_response()

    @router.put("/chat/folder-permissions")
    def upsert_folder_permission(request_body: FolderPermissionRequest) -> FolderPermissionListResponse:
        folder_path = _normalize_folder_path(request_body.path)
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail="folder not found")
        if not folder_path.is_dir():
            raise HTTPException(status_code=400, detail="path is not a directory")

        config = get_runtime_config()
        config.set_folder_permission(str(folder_path), request_body.access_level)
        return _build_folder_permission_response()

    @router.delete("/chat/folder-permissions")
    def remove_folder_permission(path: str) -> FolderPermissionListResponse:
        folder_path = _normalize_folder_path(path)
        config = get_runtime_config()
        removed = config.remove_folder_permission(str(folder_path))
        if not removed:
            raise HTTPException(status_code=404, detail="folder permission not found")
        return _build_folder_permission_response()

    @router.post("/chat", response_model_exclude_none=True)
    def chat(
        request_body: ChatRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        mempalace_adapter: MemPalaceAdapter = Depends(get_mempalace_adapter),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
        latest_plan_completion = None
        latest_self_programming = _summarize_latest_self_programming(state)

        persona_service.infer_chat_emotion(request_body.message)
        persona_system_prompt = persona_service.build_system_prompt()

        current_emotion = persona_service.profile.emotion
        style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
        style_override = style_mapper.map_from_state(current_emotion)
        expression_style_context = style_mapper.build_style_prompt(style_override)

        config = get_runtime_config()
        gateway.model = config.chat_model
        attached_folder_paths = _resolve_attachment_paths(request_body.attachments, "folder")
        attached_file_paths = _resolve_attachment_paths(request_body.attachments, "file")
        attached_image_paths = _resolve_attachment_paths(request_body.attachments, "image")

        for folder_path in _build_attachment_permission_paths(
            folder_paths=attached_folder_paths,
            file_paths=attached_file_paths,
            image_paths=attached_image_paths,
        ):
            config.set_folder_permission(folder_path, "read_only")

        file_context = _build_file_attachment_context(attached_file_paths)
        effective_user_message = request_body.message
        if file_context:
            effective_user_message = (
                f"{request_body.message}\n\n"
                "[用户附加文件内容摘录]\n"
                f"{file_context}"
            )

        tracker = _get_observability_tracker(request)
        retrieval_started_at = perf_counter()
        chat_messages, memory_context, retrieval_failed, retrieval_attempted = _resolve_mempalace_chat_context(
            user_message=request_body.message,
            mempalace_adapter=mempalace_adapter,
            memory_repository=memory_repository,
            context_limit=config.chat_context_limit,
        )
        knowledge_references = _extract_knowledge_references(memory_context)
        if retrieval_attempted:
            _record_retrieval_observability(
                tracker=tracker,
                latency_ms=(perf_counter() - retrieval_started_at) * 1000.0,
                references=knowledge_references,
                failed=retrieval_failed,
            )
        image_parts = _build_image_content_parts(
            attachments=request_body.attachments,
            image_paths=attached_image_paths,
            provider_id=config.chat_provider,
            model=config.chat_model,
            wire_api=getattr(gateway, "wire_api", "responses"),
        )
        if image_parts:
            if getattr(gateway, "wire_api", "responses") == "responses":
                user_content: str | list[dict] = [
                    {"type": "input_text", "text": effective_user_message},
                    *image_parts,
                ]
            else:
                user_content = [
                    {"type": "text", "text": effective_user_message},
                    *image_parts,
                ]
        else:
            user_content = effective_user_message
        chat_messages = _apply_user_content_to_messages(
            chat_messages,
            user_content=user_content,
        )
        instructions = build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_programming=latest_self_programming,
            user_message=request_body.message,
            current_thought=state.current_thought,
            persona_system_prompt=persona_system_prompt,
            relationship_summary=None,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
            folder_permissions=config.list_folder_permissions(),
        )
        instructions = _append_attachment_context(
            instructions,
            folder_paths=attached_folder_paths,
            file_paths=attached_file_paths,
            image_paths=attached_image_paths,
        )
        instructions = _append_skill_context(
            instructions,
            user_message=request_body.message,
            requested_skills=request_body.skills,
        )
        reasoning_state: ChatReasoningState | None = None
        reasoning_session_id: str | None = None
        if config.chat_continuous_reasoning_enabled and request_body.reasoning is not None and request_body.reasoning.enabled:
            reasoning_state = _start_reasoning_session(
                user_message=request_body.message,
                session_id=request_body.reasoning.session_id,
            )
            reasoning_session_id = reasoning_state.session_id
            instructions = _append_reasoning_instruction(
                instructions,
                reasoning_state=reasoning_state,
            )
        mcp_registry = _build_chat_mcp_registry(request_body.mcp_servers)

        assistant_message_id = f"assistant_{uuid4().hex}"
        chat_started_at = perf_counter()
        if image_parts:
            submission, output_text = _run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )
        else:
            submission, output_text = _run_chat_submission_with_tools(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                knowledge_references=knowledge_references,
                extra_tools=mcp_registry.tools,
                mcp_registry=mcp_registry,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )
        if tracker is not None:
            tracker.record_chat_latency((perf_counter() - chat_started_at) * 1000.0)

        finalized_reasoning_state = _update_reasoning_session_after_completion(
            reasoning_state=reasoning_state,
            user_message=request_body.message,
            output_text=output_text,
        )
        finalized_reasoning_session_id = (
            finalized_reasoning_state.session_id if finalized_reasoning_state is not None else None
        )
        write_success = False
        try:
            write_success = bool(
                mempalace_adapter.record_exchange(
                    request_body.message,
                    output_text,
                    assistant_message_id,
                    reasoning_session_id=finalized_reasoning_session_id,
                    reasoning_state=(
                        finalized_reasoning_state.model_dump(mode="json")
                        if finalized_reasoning_state is not None
                        else None
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace record_exchange raised unexpectedly: %s", exc)
        finally:
            if tracker is not None:
                tracker.record_write(success=write_success)
        try:
            _mirror_exchange_to_memory_repository(
                memory_repository=memory_repository,
                user_message=request_body.message,
                assistant_response=output_text,
                assistant_session_id=assistant_message_id,
                reasoning_session_id=finalized_reasoning_session_id,
                reasoning_state=finalized_reasoning_state,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mirror exchange to memory repository failed: %s", exc)
        if get_chat_knowledge_extraction_enabled():
            try:
                _extract_structured_knowledge_events(
                    memory_repository=memory_repository,
                    user_message=request_body.message,
                    assistant_response=output_text,
                    assistant_session_id=assistant_message_id,
                    personality=persona_service.profile.personality,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("structured knowledge extraction failed: %s", exc)
        latest_state = state_store.get()
        next_thought = _build_post_chat_thought(request_body.message, output_text)
        state_store.set(latest_state.model_copy(update={"current_thought": next_thought}))
        if finalized_reasoning_state is not None:
            _remember_reasoning_session_for_assistant(assistant_message_id, finalized_reasoning_state.session_id)
            submission = submission.model_copy(
                update={
                    "reasoning_session_id": finalized_reasoning_state.session_id,
                    "reasoning_state": finalized_reasoning_state,
                }
            )

        return submission

    @router.post("/chat/resume", response_model_exclude_none=True)
    def resume_chat(
        request_body: ChatResumeRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        mempalace_adapter: MemPalaceAdapter = Depends(get_mempalace_adapter),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
        latest_plan_completion = None
        latest_self_programming = _summarize_latest_self_programming(state)

        persona_service.infer_chat_emotion(request_body.message)
        persona_system_prompt = persona_service.build_system_prompt()
        current_emotion = persona_service.profile.emotion
        style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
        style_override = style_mapper.map_from_state(current_emotion)
        expression_style_context = style_mapper.build_style_prompt(style_override)

        config = get_runtime_config()
        gateway.model = config.chat_model
        tracker = _get_observability_tracker(request)
        retrieval_started_at = perf_counter()
        chat_messages, memory_context, retrieval_failed, retrieval_attempted = _resolve_mempalace_chat_context(
            user_message=request_body.message,
            mempalace_adapter=mempalace_adapter,
            memory_repository=memory_repository,
            context_limit=config.chat_context_limit,
        )
        knowledge_references = _extract_knowledge_references(memory_context)
        if retrieval_attempted:
            _record_retrieval_observability(
                tracker=tracker,
                latency_ms=(perf_counter() - retrieval_started_at) * 1000.0,
                references=knowledge_references,
                failed=retrieval_failed,
            )
        instructions = build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_programming=latest_self_programming,
            user_message=request_body.message,
            current_thought=state.current_thought,
            persona_system_prompt=persona_system_prompt,
            relationship_summary=None,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
            folder_permissions=config.list_folder_permissions(),
        )
        resume_reasoning_session_id = (
            _resolve_resume_reasoning_session_id(request_body, memory_repository=memory_repository)
            if config.chat_continuous_reasoning_enabled
            else None
        )
        resume_reasoning_state: ChatReasoningState | None = None
        if resume_reasoning_session_id is not None:
            resume_reasoning_state = _start_reasoning_session(
                user_message=request_body.message,
                session_id=resume_reasoning_session_id,
            )
            instructions = _append_reasoning_instruction(
                instructions,
                reasoning_state=resume_reasoning_state,
            )

        instructions = f"{instructions}\n\n{_build_resume_instruction(request_body.partial_content)}"
        instructions = _append_skill_context(
            instructions,
            user_message=request_body.message,
        )
        mcp_registry = _build_chat_mcp_registry([])

        chat_started_at = perf_counter()
        submission, output_text = _run_chat_submission_with_tools(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=instructions,
            assistant_message_id=request_body.assistant_message_id,
            initial_output_text=request_body.partial_content,
            knowledge_references=knowledge_references,
            extra_tools=mcp_registry.tools,
            mcp_registry=mcp_registry,
            reasoning_session_id=resume_reasoning_state.session_id if resume_reasoning_state is not None else None,
            reasoning_state=resume_reasoning_state,
        )
        if tracker is not None:
            tracker.record_chat_latency((perf_counter() - chat_started_at) * 1000.0)

        finalized_reasoning_state = _update_reasoning_session_after_completion(
            reasoning_state=resume_reasoning_state,
            user_message=request_body.message,
            output_text=output_text,
        )
        finalized_reasoning_session_id = (
            finalized_reasoning_state.session_id if finalized_reasoning_state is not None else None
        )
        write_success = False
        try:
            write_success = bool(
                mempalace_adapter.record_exchange(
                    request_body.message,
                    output_text,
                    request_body.assistant_message_id,
                    reasoning_session_id=finalized_reasoning_session_id,
                    reasoning_state=(
                        finalized_reasoning_state.model_dump(mode="json")
                        if finalized_reasoning_state is not None
                        else None
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace record_exchange raised unexpectedly: %s", exc)
        finally:
            if tracker is not None:
                tracker.record_write(success=write_success)
        try:
            _mirror_exchange_to_memory_repository(
                memory_repository=memory_repository,
                user_message=request_body.message,
                assistant_response=output_text,
                assistant_session_id=request_body.assistant_message_id,
                reasoning_session_id=finalized_reasoning_session_id,
                reasoning_state=finalized_reasoning_state,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mirror exchange to memory repository failed: %s", exc)
        if get_chat_knowledge_extraction_enabled():
            try:
                _extract_structured_knowledge_events(
                    memory_repository=memory_repository,
                    user_message=request_body.message,
                    assistant_response=output_text,
                    assistant_session_id=request_body.assistant_message_id,
                    personality=persona_service.profile.personality,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("structured knowledge extraction failed: %s", exc)
        latest_state = state_store.get()
        next_thought = _build_post_chat_thought(request_body.message, output_text)
        state_store.set(latest_state.model_copy(update={"current_thought": next_thought}))
        if finalized_reasoning_state is not None:
            _remember_reasoning_session_for_assistant(
                request_body.assistant_message_id,
                finalized_reasoning_state.session_id,
            )
            submission = submission.model_copy(
                update={
                    "reasoning_session_id": finalized_reasoning_state.session_id,
                    "reasoning_state": finalized_reasoning_state,
                }
            )

        return submission

    return router
