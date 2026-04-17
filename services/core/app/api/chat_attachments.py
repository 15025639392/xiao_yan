from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from fastapi import HTTPException

from app.llm.schemas import ChatAttachment, ChatMessage

SUPPORTED_TEXT_FILE_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".log",
    ".pdf",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
}
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_ATTACHED_FILE_BYTES = 512 * 1024
MAX_ATTACHED_IMAGE_BYTES = 4 * 1024 * 1024
MAX_ATTACHED_FILES = 6
MAX_ATTACHED_IMAGES = 4
MAX_TOTAL_FILE_CONTEXT_CHARS = 16_000


def resolve_attachment_paths(attachments: list[ChatAttachment], attachment_type: str) -> list[str]:
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


def build_attachment_permission_paths(
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


def build_file_attachment_context(file_paths: list[str]) -> str:
    if not file_paths:
        return ""
    if len(file_paths) > MAX_ATTACHED_FILES:
        raise HTTPException(status_code=400, detail=f"too many file attachments (max {MAX_ATTACHED_FILES})")

    remaining = MAX_TOTAL_FILE_CONTEXT_CHARS
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


def build_effective_user_message(*, user_message: str, file_paths: list[str]) -> str:
    file_context = build_file_attachment_context(file_paths)
    if not file_context:
        return user_message
    return (
        f"{user_message}\n\n"
        "[用户附加文件内容摘录]\n"
        f"{file_context}"
    )


def build_image_content_parts(
    *,
    attachments: list[ChatAttachment],
    image_paths: list[str],
    provider_id: str,
    model: str,
    wire_api: str,
) -> list[dict]:
    if not image_paths:
        return []
    if len(image_paths) > MAX_ATTACHED_IMAGES:
        raise HTTPException(status_code=400, detail=f"too many image attachments (max {MAX_ATTACHED_IMAGES})")
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
        if image_size > MAX_ATTACHED_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"image too large (> {MAX_ATTACHED_IMAGE_BYTES} bytes): {image_path}",
            )
        raw = resolved.read_bytes()
        data_url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"

        if wire_api == "responses":
            parts.append({"type": "input_image", "image_url": data_url})
        else:
            parts.append({"type": "image_url", "image_url": {"url": data_url}})
    return parts


def build_user_content(
    *,
    attachments: list[ChatAttachment],
    image_paths: list[str],
    provider_id: str,
    model: str,
    user_message: str,
    wire_api: str,
) -> tuple[str | list[dict], list[dict]]:
    image_parts = build_image_content_parts(
        attachments=attachments,
        image_paths=image_paths,
        provider_id=provider_id,
        model=model,
        wire_api=wire_api,
    )
    if not image_parts:
        return user_message, image_parts
    if wire_api == "responses":
        return [{"type": "input_text", "text": user_message}, *image_parts], image_parts
    return [{"type": "text", "text": user_message}, *image_parts], image_parts


def apply_user_content_to_messages(
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


def append_attachment_context(
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


def _supports_image_attachments(provider_id: str, model: str) -> bool:
    normalized_provider = (provider_id or "").strip().lower()
    normalized_model = (model or "").strip().lower()
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
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
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

    if suffix not in SUPPORTED_TEXT_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix or path.name}")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > MAX_ATTACHED_FILE_BYTES:
            return content[:MAX_ATTACHED_FILE_BYTES]
        return content
    except Exception as exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"failed to read attached file: {exception}") from exception
