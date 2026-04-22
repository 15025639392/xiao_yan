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
