from datetime import datetime, timezone

import pytest

from app.domain.models import XhsWorkDomainState, XhsWorkMemory, XhsWorkStatus
from app.usecases.xiaohongshu_publish_orchestration import (
    mark_xiaohongshu_browser_publish_success,
    mark_xiaohongshu_mcp_publish_success,
)


def _make_domain() -> XhsWorkDomainState:
    return XhsWorkDomainState(memory=XhsWorkMemory())


def test_mcp_publish_success_updates_work_memory():
    domain = _make_domain()
    draft = {
        "draft_id": "d1",
        "title": "高颜值巧克力",
        "opportunity_title": "巧克力测评",
        "source_kind": "topic",
    }
    domain.state.pending_drafts = [draft]
    domain.state.backlog_count = 1

    transition = mark_xiaohongshu_mcp_publish_success(
        domain,
        drafts=domain.state.pending_drafts,
        draft=draft,
        post_url="https://example.com/p1",
        message="ok",
        image_paths=["img1.png"],
    )

    assert transition.kind == "publishing"
    assert domain.state.status == XhsWorkStatus.IDLE
    assert len(domain.state.pending_drafts) == 0
    assert domain.memory.recent_draft_titles == ["高颜值巧克力"]
    assert domain.memory.successful_topic_titles == ["巧克力测评"]
    assert domain.memory.last_source_kind == "topic"


def test_browser_publish_success_updates_work_memory():
    domain = _make_domain()
    draft = {
        "draft_id": "d2",
        "title": "春日穿搭",
        "opportunity_title": "OOTD活动",
        "source_kind": "activity",
    }
    domain.state.pending_drafts = [draft]
    domain.state.backlog_count = 1

    transition = mark_xiaohongshu_browser_publish_success(
        domain,
        drafts=domain.state.pending_drafts,
        draft=draft,
        post_url="https://example.com/p2",
        current_focus="browser ok",
    )

    assert transition.kind == "publishing"
    assert domain.memory.recent_draft_titles == ["春日穿搭"]
    assert domain.memory.successful_topic_titles == ["OOTD活动"]
    assert domain.memory.last_source_kind == "activity"


def test_publish_success_caps_memory_at_10_entries():
    domain = _make_domain()
    domain.memory.recent_draft_titles = [f"title-{i}" for i in range(10)]
    domain.memory.successful_topic_titles = [f"topic-{i}" for i in range(10)]

    draft = {
        "draft_id": "d3",
        "title": "new-title",
        "opportunity_title": "new-topic",
        "source_kind": "topic",
    }
    domain.state.pending_drafts = [draft]
    domain.state.backlog_count = 1

    mark_xiaohongshu_mcp_publish_success(
        domain,
        drafts=domain.state.pending_drafts,
        draft=draft,
        post_url="https://example.com/p3",
        message="ok",
        image_paths=[],
    )

    assert domain.memory.recent_draft_titles == [f"title-{i}" for i in range(1, 10)] + ["new-title"]
    assert domain.memory.successful_topic_titles == [f"topic-{i}" for i in range(1, 10)] + ["new-topic"]


def test_publish_success_ignores_empty_draft_fields():
    domain = _make_domain()
    draft = {
        "draft_id": "d4",
        "title": "",
        "opportunity_title": "",
        "source_kind": "",
    }
    domain.state.pending_drafts = [draft]
    domain.state.backlog_count = 1

    mark_xiaohongshu_mcp_publish_success(
        domain,
        drafts=domain.state.pending_drafts,
        draft=draft,
        post_url="https://example.com/p4",
        message="ok",
        image_paths=[],
    )

    assert domain.memory.recent_draft_titles == []
    assert domain.memory.successful_topic_titles == []
    assert domain.memory.last_source_kind == ""
