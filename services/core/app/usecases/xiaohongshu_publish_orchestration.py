from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.domain.models import XhsWorkDomainState, XhsWorkStatus


@dataclass(frozen=True)
class XiaohongshuPublishTransition:
    kind: str
    title: str
    data: dict[str, Any]


def reset_xiaohongshu_publish_to_idle(domain: XhsWorkDomainState) -> XiaohongshuPublishTransition:
    domain.state.status = XhsWorkStatus.IDLE
    domain.state.current_focus = "草稿队列为空"
    domain.state.next_recommended_action = ""
    return XiaohongshuPublishTransition(kind="idle", title="无草稿可发", data={})


def mark_xiaohongshu_publish_blocked(
    domain: XhsWorkDomainState,
    *,
    bottleneck: str,
    title: str,
    data: dict[str, Any],
) -> XiaohongshuPublishTransition:
    now = datetime.now(timezone.utc)
    domain.state.status = XhsWorkStatus.BLOCKED
    domain.state.current_bottleneck = bottleneck
    domain.state.blocked_at = now
    domain.state.blocked_reason = bottleneck
    domain.state.next_recommended_action = ""
    return XiaohongshuPublishTransition(kind="publishing", title=title, data=data)


def mark_xiaohongshu_publish_review_ready(
    domain: XhsWorkDomainState,
    *,
    draft: dict[str, Any],
    session_id: str,
    focus: str,
    next_action: str,
    status: str,
    uploaded_image_count: int,
) -> XiaohongshuPublishTransition:
    draft["status"] = "ready_for_review"
    domain.state.pending_drafts[0] = draft
    domain.state.status = XhsWorkStatus.REVIEWING
    domain.state.current_bottleneck = ""
    domain.state.current_focus = focus
    domain.state.next_recommended_action = next_action
    domain.state.review_session_id = session_id
    domain.state.review_started_at = datetime.now(timezone.utc)
    return XiaohongshuPublishTransition(
        kind="publishing",
        title="已准备到发布前",
        data={"status": status, "uploaded_image_count": uploaded_image_count},
    )


def mark_xiaohongshu_mcp_publish_success(
    domain: XhsWorkDomainState,
    *,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    post_url: str,
    message: str,
    image_paths: list[str],
) -> XiaohongshuPublishTransition:
    published_entry = _consume_pending_draft(domain, drafts=drafts, draft=draft, post_url=post_url)
    domain.state.current_bottleneck = ""
    domain.state.current_focus = "已通过 MCP 自动生成封面并发布图文"
    domain.state.next_recommended_action = ""
    return XiaohongshuPublishTransition(
        kind="publishing",
        title=f"MCP 发布成功：{str(draft.get('title', ''))[:20]}",
        data={
            "published": published_entry,
            "message": message,
            "image_paths": image_paths,
        },
    )


def mark_xiaohongshu_browser_publish_success(
    domain: XhsWorkDomainState,
    *,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    post_url: str,
    current_focus: str,
) -> XiaohongshuPublishTransition:
    published_entry = _consume_pending_draft(domain, drafts=drafts, draft=draft, post_url=post_url)
    domain.state.current_focus = current_focus
    domain.state.next_recommended_action = ""
    return XiaohongshuPublishTransition(
        kind="publishing",
        title=f"发布成功：{str(draft.get('title', ''))[:20]}",
        data={"published": published_entry},
    )


def _consume_pending_draft(
    domain: XhsWorkDomainState,
    *,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    post_url: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    published_entry = {
        "draft_id": draft.get("draft_id"),
        "title": draft.get("title"),
        "opportunity_title": draft.get("opportunity_title", ""),
        "source_kind": draft.get("source_kind", ""),
        "published_at": now.isoformat(),
        "post_url": post_url,
        "metrics": {},
    }
    domain.state.pending_drafts = drafts[1:]
    domain.state.published_history = (domain.state.published_history + [published_entry])[-20:]
    domain.state.last_published_at = now
    domain.state.backlog_count = len(domain.state.pending_drafts)
    domain.state.status = XhsWorkStatus.IDLE
    domain.state.current_bottleneck = ""
    _update_work_memory_on_publish(domain, draft)
    return published_entry


def _update_work_memory_on_publish(domain: XhsWorkDomainState, draft: dict[str, Any]) -> None:
    title = str(draft.get("title", "")).strip()
    opportunity_title = str(draft.get("opportunity_title", "")).strip()
    source_kind = str(draft.get("source_kind", "")).strip()
    if title:
        domain.memory.recent_draft_titles = (domain.memory.recent_draft_titles + [title])[-10:]
    if opportunity_title:
        domain.memory.successful_topic_titles = (domain.memory.successful_topic_titles + [opportunity_title])[-10:]
    if source_kind:
        domain.memory.last_source_kind = source_kind
