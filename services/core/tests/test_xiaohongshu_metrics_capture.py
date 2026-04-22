import pytest

from app.usecases.xiaohongshu_metrics_capture import extract_metrics_from_text


def test_extract_metrics_from_text_parses_like_and_collect():
    raw = """
    小红书笔记
    点赞数: 1.2万
    收藏数: 8000
    评论数: 300
    分享数: 120
    浏览数: 10万
    """
    metrics = extract_metrics_from_text(raw)
    assert metrics.like_count == "1.2万"
    assert metrics.collect_count == "8000"
    assert metrics.comment_count == "300"
    assert metrics.share_count == "120"
    assert metrics.view_count == "10万"


def test_extract_metrics_from_text_parses_w_variant():
    raw = "获赞: 500w  评论数: 20"
    metrics = extract_metrics_from_text(raw)
    assert metrics.like_count == "500w"
    assert metrics.comment_count == "20"


def test_extract_metrics_from_text_missing_fields():
    raw = "点赞数: 100"
    metrics = extract_metrics_from_text(raw)
    assert metrics.like_count == "100"
    assert metrics.collect_count is None
    assert metrics.comment_count is None


def test_extract_metrics_from_text_no_metrics():
    raw = "这是一段没有任何指标的文本\n就随便写写"
    metrics = extract_metrics_from_text(raw)
    assert metrics.like_count is None
    assert metrics.collect_count is None
