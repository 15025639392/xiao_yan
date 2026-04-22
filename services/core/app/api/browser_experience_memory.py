from __future__ import annotations

from typing import Any, Callable

from app.memory.repository import MemoryRepository
from app.memory.storage_models import MemoryEvent

_memory_repository_getter: Callable[[], MemoryRepository | None] | None = None


def set_browser_memory_repository_getter(getter: Callable[[], MemoryRepository | None]) -> None:
    global _memory_repository_getter
    _memory_repository_getter = getter


def save_browser_experience(
    capability: str,
    formatted_result: dict[str, Any],
) -> None:
    if capability not in {"browser.snapshot", "browser.extract", "browser.open"}:
        return

    try:
        if _memory_repository_getter is None:
            return

        repo = _memory_repository_getter()
        if repo is None:
            return

        text = _generate_browser_experience_text(capability, formatted_result)
        if not text:
            return

        if capability == "browser.snapshot":
            url = formatted_result.get("url", "")
            _save_browser_experience_event(
                repo,
                content=text,
                facet="browser_experience",
                tags=["browser", "snapshot", "webpage"],
                source_ref=url or None,
            )
            _save_xhs_browse_event_if_needed(
                repo,
                url=url,
                title=formatted_result.get("title", ""),
                text_content=formatted_result.get("text_content", ""),
                tags=["browser", "snapshot", "xiaohongshu"],
            )
        elif capability == "browser.extract":
            url = formatted_result.get("source_url", "")
            _save_browser_experience_event(
                repo,
                content=text,
                facet="browser_experience",
                tags=["browser", "extract", "webpage"],
                source_ref=url or None,
            )
            _save_xhs_browse_event_if_needed(
                repo,
                url=url,
                title="",
                text_content=formatted_result.get("content", ""),
                tags=["browser", "extract", "xiaohongshu"],
            )
        elif capability == "browser.open":
            url = formatted_result.get("url", "") or ""
            _save_xhs_browse_event_if_needed(
                repo,
                url=url,
                title=formatted_result.get("title", "") or "",
                text_content=formatted_result.get("text_content", ""),
                tags=["browser", "open", "xiaohongshu"],
            )
    except Exception:
        pass


def _save_browser_experience_event(
    repo: MemoryRepository,
    *,
    content: str,
    facet: str,
    tags: list[str],
    source_ref: str | None,
) -> None:
    repo.save_event(
        MemoryEvent(
            kind="autobio",
            content=content,
            source_context="autobio",
            namespace="autobio",
            facet=facet,
            tags=tags,
            source_ref=source_ref,
        )
    )


def _save_xhs_browse_event_if_needed(
    repo: MemoryRepository,
    *,
    url: str,
    title: str,
    text_content: str,
    tags: list[str],
) -> None:
    if "xiaohongshu.com" not in url and "xhslink.com" not in url:
        return

    xhs_text = _generate_xhs_browse_text(url, title, text_content)
    if not xhs_text:
        return

    _save_browser_experience_event(
        repo,
        content=xhs_text,
        facet="xhs_browse",
        tags=tags,
        source_ref=url or None,
    )


def _generate_browser_experience_text(capability: str, result: dict[str, Any]) -> str:
    if capability == "browser.snapshot":
        url = result.get("url", "")
        title = result.get("title", "")
        text_content = result.get("text_content", "")
        if not text_content:
            return ""
        preview = text_content[:200].replace("\n", " ").strip()
        suffix = "..." if len(text_content) > 200 else ""
        return f"访问了 {url}，看到了「{title}」，内容摘要：{preview}{suffix}"

    if capability == "browser.extract":
        url = result.get("source_url", "")
        target = result.get("target", "")
        content = result.get("content", "")
        if not content:
            return ""
        preview = content[:200].replace("\n", " ").strip()
        suffix = "..." if len(content) > 200 else ""
        return f"在 {url} 上用选择器「{target}」提取内容，得到：{preview}{suffix}"

    return ""


def _generate_xhs_browse_text(url: str, title: str, text_content: str) -> str:
    if not title and not text_content:
        return ""
    preview = (text_content or title)[:150].replace("\n", " ").strip()
    suffix = "..." if len(text_content or title) > 150 else ""
    label = f"「{title}」" if title else url
    return f"浏览了小红书页面 {label}，内容摘要：{preview}{suffix}"
