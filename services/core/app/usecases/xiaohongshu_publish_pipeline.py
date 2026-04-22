from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
)
from app.domain.models import XhsWorkDomainState, XhsWorkStatus
from app.external_executors.xiaohongshu_mcp_client import XiaohongshuMcpClient
from app.usecases.xiaohongshu_browser_publish_executor import (
    XiaohongshuBrowserPublishExecution,
    execute_xiaohongshu_browser_publish,
    resolve_xiaohongshu_publish_selector,
)
from app.usecases.xiaohongshu_browser_publish_review import (
    evaluate_xiaohongshu_browser_review_preparation,
)
from app.usecases.xiaohongshu_cover_image import (
    generate_xiaohongshu_cover_image,
)
from app.usecases.xiaohongshu_publish_orchestration import (
    XiaohongshuPublishTransition,
    mark_xiaohongshu_browser_publish_success,
    mark_xiaohongshu_mcp_publish_success,
    mark_xiaohongshu_publish_blocked,
    mark_xiaohongshu_publish_review_ready,
    mark_xiaohongshu_text_image_review,
)
from app.usecases.xiaohongshu_publish_preparation import (
    build_xiaohongshu_browser_publish_image_paths,
    find_xiaohongshu_publish_button,
    prepare_xiaohongshu_text_image_cards_for_draft,
)
from app.usecases.xiaohongshu_publish_via_mcp import (
    XiaohongshuPublishViaMcpResponse,
    publish_xiaohongshu_image_post_via_mcp,
)
from app.usecases.xiaohongshu_text_image_autofill import (
    autofill_xiaohongshu_text_image_cards,
)


@dataclass(frozen=True)
class XiaohongshuPublishPipelineResult:
    transition: XiaohongshuPublishTransition
    updated_selector: str | None = None


_MCP_FAILURE_STATUSES = {
    "publisher_disabled",
    "service_unreachable",
    "publish_failed",
    "cover_generation_failed",
    "cover_generation_unavailable",
}


def run_xiaohongshu_publish_pipeline(
    *,
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    mcp_client: XiaohongshuMcpClient,
    requires_manual_review: bool,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishPipelineResult:
    mcp_result = None if requires_manual_review else _try_mcp_publish(draft, mcp_client)
    if mcp_result is not None and mcp_result.status not in _MCP_FAILURE_STATUSES:
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_mcp_publish_success(
                domain,
                drafts=drafts,
                draft=draft,
                post_url=mcp_result.post_url or publish_url,
                message=mcp_result.message,
                image_paths=mcp_result.image_paths,
            ),
        )

    image_paths = _prepare_browser_image_paths(draft, mcp_result)
    return _run_browser_publish_path(
        domain=domain,
        drafts=drafts,
        draft=draft,
        image_paths=image_paths,
        requires_manual_review=requires_manual_review,
        publish_url=publish_url,
        call_browser_capability=call_browser_capability,
        close_session=close_session,
    )


def _try_mcp_publish(
    draft: dict[str, Any],
    mcp_client: XiaohongshuMcpClient,
) -> XiaohongshuPublishViaMcpResponse | None:
    title = str(draft.get("title", "")).strip()
    body = str(draft.get("body", "")).strip()
    if not title or not body:
        return None
    raw_image_paths = draft.get("image_paths")
    image_paths = raw_image_paths if isinstance(raw_image_paths, list) else []
    return publish_xiaohongshu_image_post_via_mcp(
        title=title,
        body=body,
        image_paths=image_paths,
        client=mcp_client,
    )


def _prepare_browser_image_paths(
    draft: dict[str, Any],
    mcp_result: XiaohongshuPublishViaMcpResponse | None,
) -> list[str]:
    if mcp_result is not None:
        paths = [str(item).strip() for item in mcp_result.image_paths if str(item).strip()]
        if paths:
            return paths
    return build_xiaohongshu_browser_publish_image_paths(
        draft,
        generate_cover_image=generate_xiaohongshu_cover_image,
    )


def _run_browser_publish_path(
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    image_paths: list[str],
    requires_manual_review: bool,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishPipelineResult:
    selector_resolution = resolve_xiaohongshu_publish_selector(
        requires_manual_review=requires_manual_review,
        auto_publish_selector=domain.profile.auto_publish_selector,
        find_publish_button=lambda: find_xiaohongshu_publish_button(
            publish_url=publish_url,
            call_browser_capability=call_browser_capability,
            close_session=close_session,
        ),
        prepare_text_image_cards=lambda: prepare_xiaohongshu_text_image_cards_for_draft(
            draft,
            autofill_cards=autofill_xiaohongshu_text_image_cards,
        ),
    )

    if selector_resolution.text_image_result is not None:
        return _handle_text_image_result(
            domain, selector_resolution.text_image_result, close_session
        )

    if selector_resolution.blocked_reason:
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck=selector_resolution.blocked_reason,
                title="发布失败",
                data={"error": "publish button not found"},
            ),
        )

    selector = selector_resolution.selector
    updated_selector: str | None = None
    if selector and selector != domain.profile.auto_publish_selector and not requires_manual_review:
        updated_selector = selector

    execution = execute_xiaohongshu_browser_publish(
        title=str(draft.get("title", "")),
        body=str(draft.get("body", "")),
        selector=selector,
        image_paths=image_paths,
        open_publish_page=lambda: call_browser_capability(
            "browser.open",
            {"url": publish_url, "headless": False},
            timeout_seconds=20.0,
        ),
        publish_to_page=lambda session_id, title, body, publish_selector, image_paths: call_browser_capability(
            "browser.publish",
            {
                "session_id": session_id,
                "title": title,
                "body": body,
                "publish_selector": publish_selector,
                "image_paths": image_paths,
            },
            timeout_seconds=20.0,
        ),
    )

    result = _handle_execution_result(
        domain=domain,
        drafts=drafts,
        draft=draft,
        execution=execution,
        image_paths=image_paths,
        requires_manual_review=requires_manual_review,
        publish_url=publish_url,
        call_browser_capability=call_browser_capability,
        close_session=close_session,
    )
    result = XiaohongshuPublishPipelineResult(
        transition=result.transition,
        updated_selector=updated_selector or result.updated_selector,
    )
    return result


def _handle_text_image_result(
    domain: XhsWorkDomainState,
    text_image_result: dict[str, str],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishPipelineResult:
    status = text_image_result.get("status", "missing_editor")
    if status == "browser_unavailable":
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck="浏览器器官不可用",
                title="发布失败",
                data={"error": "browser organ unavailable"},
            ),
        )
    return XiaohongshuPublishPipelineResult(
        transition=mark_xiaohongshu_text_image_review(
            domain,
            focus=str(
                text_image_result.get("focus")
                or "已进入补图阶段，等待图片生成后再继续发布"
            ),
            status=status,
            message=text_image_result.get("message", ""),
        ),
    )


def _handle_execution_result(
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    execution: XiaohongshuBrowserPublishExecution,
    image_paths: list[str],
    requires_manual_review: bool,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishPipelineResult:
    session_id = execution.session_id
    if execution.error:
        if session_id:
            close_session(session_id)
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck=execution.blocked_reason or "发布失败",
                title="发布失败",
                data={"error": execution.error},
            ),
        )

    if not session_id:
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck=execution.blocked_reason or "无法打开发布页",
                title="打开发布页失败",
                data={},
            ),
        )

    publish_result = execution.publish_result or {}
    publish_clicked = publish_result.get("publish_clicked", False)
    status = publish_result.get("status", "unknown")

    if requires_manual_review:
        transition = _handle_review_path(
            domain=domain,
            draft=draft,
            session_id=session_id,
            publish_result=publish_result,
            status=status,
            image_paths=image_paths,
            publish_url=publish_url,
            call_browser_capability=call_browser_capability,
            close_session=close_session,
        )
        return XiaohongshuPublishPipelineResult(transition=transition)

    if publish_clicked:
        close_session(session_id)
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_browser_publish_success(
                domain,
                drafts=drafts,
                draft=draft,
                post_url=publish_url,
                current_focus="已自动补封面并发布成功" if image_paths else "已完成补图并发布成功",
            ),
        )

    close_session(session_id)
    return XiaohongshuPublishPipelineResult(
        transition=mark_xiaohongshu_publish_blocked(
            domain,
            bottleneck=f"无法点击发布按钮（status={status}）",
            title="发布未完成",
            data={"status": status},
        ),
    )


def _handle_review_path(
    domain: XhsWorkDomainState,
    draft: dict[str, Any],
    session_id: str,
    publish_result: dict[str, Any],
    status: str,
    image_paths: list[str],
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishTransition:
    if status == "awaiting_image_upload" and not image_paths:
        text_image_result = prepare_xiaohongshu_text_image_cards_for_draft(
            draft,
            autofill_cards=autofill_xiaohongshu_text_image_cards,
        )
        if text_image_result is not None:
            review_status = text_image_result.get("status", "missing_editor")
            if review_status == "browser_unavailable":
                close_session(session_id)
                return mark_xiaohongshu_publish_blocked(
                    domain,
                    bottleneck="浏览器器官不可用",
                    title="发布失败",
                    data={"error": "browser organ unavailable"},
                )
            close_session(session_id)
            return mark_xiaohongshu_text_image_review(
                domain,
                focus=str(
                    text_image_result.get("focus")
                    or "已进入补图阶段，等待图片生成后再继续发布"
                ),
                status=review_status,
                message=text_image_result.get("message", ""),
            )

    review_preparation = evaluate_xiaohongshu_browser_review_preparation(
        publish_result=publish_result,
        requested_image_paths=image_paths,
    )
    if review_preparation.ready:
        return mark_xiaohongshu_publish_review_ready(
            domain,
            draft=draft,
            session_id=session_id,
            focus=review_preparation.focus,
            next_action=review_preparation.next_action,
            status=status,
            uploaded_image_count=int(publish_result.get("uploaded_image_count", 0) or 0),
        )

    close_session(session_id)
    return mark_xiaohongshu_publish_blocked(
        domain,
        bottleneck=review_preparation.blocking_reason or "还没准备到可发布状态",
        title="发布前准备失败",
        data={"status": status},
    )
