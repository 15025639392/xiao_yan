from app.domain.models import XhsWorkPolicy
from app.usecases.xiaohongshu_policy import (
    can_post_today,
    check_draft_against_policy,
)


def test_no_violations():
    policy = XhsWorkPolicy()
    # Body must be >= min_body_chars default (50 chars)
    body = "开箱第一眼就被惊艳到了，包装非常精致，内容也很用心，整体感觉非常不错，值得推荐给朋友们试试看，体验超棒。"
    assert len(body) >= 50
    draft = {"title": "巧克力礼盒", "body": body}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is True
    assert result.errors == []
    assert result.warnings == []


def test_forbidden_keyword_in_body():
    policy = XhsWorkPolicy(forbidden_keywords=["广告", "推广"])
    draft = {"title": "巧克力", "body": "这是广告内容"}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is False
    assert any("广告" in e.message for e in result.errors)


def test_forbidden_keyword_in_title():
    policy = XhsWorkPolicy(forbidden_keywords=["违禁词"])
    draft = {"title": "违禁词内容", "body": "正文没问题"}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is False
    assert any("违禁词" in e.message for e in result.errors)


def test_required_keyword_missing():
    policy = XhsWorkPolicy(required_keywords=["分享", "推荐"])
    draft = {"title": "巧克力", "body": "非常好吃的巧克力"}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is True  # missing required keywords are warnings, not errors
    assert any("分享" in w.message for w in result.warnings)


def test_body_too_short():
    policy = XhsWorkPolicy(min_body_chars=50)
    draft = {"title": "标题", "body": "太短了"}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is True  # min chars is a warning
    assert any("过短" in w.message for w in result.warnings)


def test_body_too_long_is_truncated():
    policy = XhsWorkPolicy(max_body_chars=10)
    draft = {"title": "标题", "body": "这是一段很长的正文内容"}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is False
    assert any("过长" in e.message for e in result.errors)
    # body should be truncated
    assert len(draft["body"]) <= 10


def test_max_body_chars_zero_means_no_limit():
    policy = XhsWorkPolicy(max_body_chars=0)
    draft = {"title": "标题", "body": "x" * 10000}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is True


def test_can_post_today_within_limit():
    policy = XhsWorkPolicy(max_posts_per_day=3)
    assert can_post_today(0, policy) is True
    assert can_post_today(2, policy) is True
    assert can_post_today(3, policy) is False


def test_can_post_today_no_limit():
    policy = XhsWorkPolicy(max_posts_per_day=0)
    assert can_post_today(999, policy) is True


def test_multiple_violations():
    policy = XhsWorkPolicy(
        forbidden_keywords=["违禁"],
        required_keywords=["必须"],
        min_body_chars=100,
        max_body_chars=5,
    )
    # Body is both > 5 chars (triggers max_body_chars error) and has forbidden keyword
    draft = {"title": "违禁内容", "body": "这是一段超过5个字符的正文内容用来测试"}
    result = check_draft_against_policy(draft, policy)
    assert result.ok is False
    assert len(result.errors) == 2  # forbidden + max chars
    assert len(result.warnings) == 2  # required + min chars
