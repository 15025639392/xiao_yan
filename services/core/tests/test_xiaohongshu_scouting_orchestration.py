from datetime import datetime, timezone

from app.domain.models import XhsWorkStatus
from app.usecases.xiaohongshu_scouting_orchestration import (
    apply_xiaohongshu_scouting_result,
    is_xiaohongshu_creator_home_login_required,
)


def test_login_required_detects_login_page_without_topic_markers():
    text = "请先登录 小红书创作服务平台 账号登录 手机号登录"
    assert is_xiaohongshu_creator_home_login_required(text) is True


def test_apply_scouting_result_updates_domain_and_returns_action_data():
    domain = type(
        "Domain",
        (),
        {
            "profile": type("Profile", (), {"account_name": ""})(),
            "state": type(
                "State",
                (),
                {
                    "status": XhsWorkStatus.SCOUTING,
                    "last_scouting_at": None,
                    "current_focus": "",
                    "current_bottleneck": "",
                    "last_scouting_data": {},  # required by update_xiaohongshu_world_snapshot
                },
            )(),
        },
    )()
    extracted = type(
        "Extracted",
        (),
        {
            "topics": [type("Topic", (), {"topic": "巧克力", "participation_count": "1万", "view_count": "10万"})()],
            "activities": [type("Activity", (), {"title": "大赛", "date_range": "4月", "incentive_hint": "奖金"})()],
            "account_name": "小晏",
        },
    )()

    outcome = apply_xiaohongshu_scouting_result(
        domain,
        extracted=extracted,
        text_content="页面文本",
        now=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    assert domain.profile.account_name == "小晏"
    assert domain.state.status == XhsWorkStatus.DRAFTING
    assert "发现 1 个话题、1 个活动" == domain.state.current_focus
    assert outcome.action_title == "侦察完成：1 个话题"
    assert outcome.last_scouting_data["topics"][0]["topic"] == "巧克力"
    # Snapshot fields are persisted
    assert outcome.last_scouting_data["version"] == 1
    assert outcome.last_scouting_data["topic_count"] == 1
    assert outcome.last_scouting_data["activity_count"] == 1
    assert outcome.last_scouting_data["captured_at"] == "2026-04-22T00:00:00+00:00"


def test_world_snapshot_truncates_raw_text():
    from app.domain.models import XhsWorkDomainState
    from app.usecases.xiaohongshu_scouting_orchestration import update_xiaohongshu_world_snapshot

    domain = XhsWorkDomainState()
    domain.state.last_scouting_data = {"version": 0}  # prev version = 0

    long_text = "x" * 5000
    snapshot = update_xiaohongshu_world_snapshot(
        domain,
        topics=[{"topic": "#test", "participation_count": "100", "view_count": None}],
        activities=[],
        account_name="tester",
        raw_text=long_text,
        now=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    # raw_text is truncated to last 2000 chars
    assert len(snapshot.raw_text_truncated) == 2000
    assert snapshot.raw_text_truncated == "x" * 2000
    # version is incremented
    assert snapshot.version == 1
    # state is updated
    assert domain.state.last_scouting_data["version"] == 1
    assert domain.state.last_scouting_data["topic_count"] == 1
