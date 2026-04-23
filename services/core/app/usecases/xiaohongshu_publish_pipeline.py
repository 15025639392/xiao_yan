from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.domain.models import XhsPublishMode, XhsWorkDomainState
from app.usecases.xiaohongshu_browser_publish_executor import (
    XiaohongshuBrowserPublishExecution,
    execute_xiaohongshu_browser_publish,
)
from app.usecases.xiaohongshu_browser_publish_review import (
    evaluate_xiaohongshu_browser_review_preparation,
)
from app.usecases.xiaohongshu_cover_image import (
    generate_xiaohongshu_cover_image,
)
from app.usecases.xiaohongshu_publish_orchestration import (
    XiaohongshuPublishTransition,
    mark_xiaohongshu_publish_blocked,
    mark_xiaohongshu_publish_review_ready,
    mark_xiaohongshu_browser_publish_success,
)
from app.usecases.xiaohongshu_publish_preparation import (
    build_xiaohongshu_browser_publish_image_paths,
    find_xiaohongshu_publish_button,
    prepare_xiaohongshu_publish_draft,
)


@dataclass(frozen=True)
class XiaohongshuPublishPipelineResult:
    transition: XiaohongshuPublishTransition


def run_xiaohongshu_publish_pipeline(
    *,
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    publish_mode: XhsPublishMode,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishPipelineResult:
    prepared_draft = prepare_xiaohongshu_publish_draft(draft)
    image_paths = _prepare_browser_image_paths(prepared_draft)
    publish_selector = _resolve_publish_selector(
        publish_mode=publish_mode,
        publish_url=publish_url,
        call_browser_capability=call_browser_capability,
        close_session=close_session,
    )
    if publish_mode == XhsPublishMode.AUTO and not publish_selector:
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck="找不到发布按钮",
                title="自动发布失败",
                data={"error": "publish button not found"},
            ),
        )
    return _run_browser_publish_path(
        domain=domain,
        drafts=drafts,
        draft=prepared_draft,
        image_paths=image_paths,
        publish_mode=publish_mode,
        publish_selector=publish_selector,
        publish_url=publish_url,
        call_browser_capability=call_browser_capability,
        close_session=close_session,
    )


def _prepare_browser_image_paths(
    draft: dict[str, Any],
) -> list[str]:
    return build_xiaohongshu_browser_publish_image_paths(
        draft,
        generate_cover_image=generate_xiaohongshu_cover_image,
    )


def _resolve_publish_selector(
    *,
    publish_mode: XhsPublishMode,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> str:
    if publish_mode != XhsPublishMode.AUTO:
        return ""
    return (
        find_xiaohongshu_publish_button(
            publish_url=publish_url,
            call_browser_capability=call_browser_capability,
            close_session=close_session,
        )
        or ""
    )


def _run_browser_publish_path(
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    image_paths: list[str],
    publish_mode: XhsPublishMode,
    publish_selector: str,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> XiaohongshuPublishPipelineResult:
    if not image_paths:
        return XiaohongshuPublishPipelineResult(
            transition=mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck="缺少可上传封面",
                title="发布失败",
                data={"error": "missing cover image"},
            ),
        )

    execution = execute_xiaohongshu_browser_publish(
        title=str(draft.get("title", "")),
        body=str(draft.get("body", "")),
        selector=publish_selector,
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
        publish_mode=publish_mode,
        publish_url=publish_url,
        call_browser_capability=call_browser_capability,
        close_session=close_session,
    )
    return result


def _handle_execution_result(
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    execution: XiaohongshuBrowserPublishExecution,
    image_paths: list[str],
    publish_mode: XhsPublishMode,
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
    status = publish_result.get("status", "unknown")

    if publish_mode == XhsPublishMode.AUTO:
        transition = _handle_auto_publish_path(
            domain=domain,
            drafts=drafts,
            draft=draft,
            session_id=session_id,
            publish_result=publish_result,
            status=status,
            image_paths=image_paths,
            publish_url=publish_url,
            close_session=close_session,
        )
    else:
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


def _handle_auto_publish_path(
    *,
    domain: XhsWorkDomainState,
    drafts: list[dict[str, Any]],
    draft: dict[str, Any],
    session_id: str,
    publish_result: dict[str, Any],
    status: str,
    image_paths: list[str],
    publish_url: str,
    close_session: Callable[[str], None],
) -> XiaohongshuPublishTransition:
    review_preparation = evaluate_xiaohongshu_browser_review_preparation(
        publish_result=publish_result,
        requested_image_paths=image_paths,
    )
    click_error = str(publish_result.get("click_error", "") or "").strip()
    publish_clicked = bool(publish_result.get("publish_clicked", False))

    if click_error:
        close_session(session_id)
        return mark_xiaohongshu_publish_blocked(
            domain,
            bottleneck="无法点击发布按钮",
            title="自动发布失败",
            data={"error": click_error},
        )

    if not review_preparation.ready:
        close_session(session_id)
        return mark_xiaohongshu_publish_blocked(
            domain,
            bottleneck=review_preparation.blocking_reason or "还没准备到可发布状态",
            title="自动发布失败",
            data={"status": status},
        )

    if not publish_clicked:
        close_session(session_id)
        return mark_xiaohongshu_publish_blocked(
            domain,
            bottleneck="无法点击发布按钮",
            title="自动发布失败",
            data={"status": status},
        )

    close_session(session_id)
    return mark_xiaohongshu_browser_publish_success(
        domain,
        drafts=drafts,
        draft=draft,
        post_url=publish_url,
        current_focus="已自动发布到小红书",
        continue_publishing=True,
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
        close_session(session_id)
        return mark_xiaohongshu_publish_blocked(
            domain,
            bottleneck="缺少可上传封面",
            title="发布失败",
            data={"error": "missing cover image"},
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
