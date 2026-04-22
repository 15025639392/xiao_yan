from app.usecases.xiaohongshu_draft_generation import (
    build_xiaohongshu_opportunity_items,
    generate_xiaohongshu_draft_from_opportunity,
    _parse_count,
)


def test_parse_count():
    assert _parse_count("1.2万") == 12000.0
    assert _parse_count("500") == 500.0
    assert _parse_count("1.5w") == 15000.0
    assert _parse_count(None) == 0.0
    assert _parse_count("invalid") == 0.0


def test_build_opportunity_items_sorts_by_past_engagement():
    history = [
        {
            "draft_id": "d1",
            "opportunity_title": "#高颜值巧克力",
            "metrics": {"like_count": "100", "collect_count": "50", "comment_count": "10"},
        },
        {
            "draft_id": "d2",
            "opportunity_title": "#春日穿搭",
            "metrics": {"like_count": "10", "collect_count": "5", "comment_count": "1"},
        },
    ]
    items = build_xiaohongshu_opportunity_items(
        {
            "topics": [
                {"topic": "#春日穿搭", "participation_count": "5000"},
                {"topic": "#高颜值巧克力", "participation_count": "1万"},
            ],
            "activities": [],
        },
        published_history=history,
    )

    # #高颜值巧克力 has higher engagement → should come first
    assert items[0]["title"] == "#高颜值巧克力"
    assert items[1]["title"] == "#春日穿搭"
    # High-engagement topics should include the engagement hint
    assert "往期互动" in items[0]["summary"]


def test_build_opportunity_items_deprioritizes_recently_used():
    items = build_xiaohongshu_opportunity_items(
        {
            "topics": [
                {"topic": "#巧克力", "participation_count": "1万"},
                {"topic": "#零食", "participation_count": "2万"},
            ],
            "activities": [],
        },
        recent_topics=["#巧克力"],
    )

    # #零食 has higher participation but #巧克力 was recently used → #零食 first
    assert items[0]["title"] == "#零食"
    assert items[1]["title"] == "#巧克力"


def test_build_opportunity_items_includes_view_count():
    items = build_xiaohongshu_opportunity_items(
        {
            "topics": [{"topic": "#咖啡", "participation_count": "5千", "view_count": "50万"}],
            "activities": [],
        },
    )

    assert "参与5千" in items[0]["summary"]
    assert "浏览50万" in items[0]["summary"]


def test_build_opportunity_items_merges_topics_and_activities():
    items = build_xiaohongshu_opportunity_items(
        {
            "topics": [{"topic": "巧克力", "participation_count": "1万"}],
            "activities": [{"title": "大赛", "date_range": "4月", "incentive_hint": "奖金"}],
        }
    )

    assert items[0]["source_kind"] == "topic"
    assert items[0]["title"] == "巧克力"
    assert items[1]["source_kind"] == "activity"
    assert items[1]["title"] == "大赛"


def test_generate_draft_from_opportunity_uses_gateway_output_when_parseable():
    gateway = type(
        "Gateway",
        (),
        {
            "create_response": lambda self, messages, instructions: type(
                "Result",
                (),
                {"output_text": "标题：巧克力礼盒也太绝了\n正文：开箱第一眼就被包装惊到了。"},
            )(),
        },
    )()

    outcome = generate_xiaohongshu_draft_from_opportunity(
        {"source_kind": "topic", "title": "巧克力礼盒", "summary": "参与人数: 1万"},
        gateway=gateway,
        build_prompt=lambda opportunity: "prompt",
    )

    assert outcome.draft["title"] == "巧克力礼盒也太绝了"
    assert "开箱第一眼" in outcome.draft["body"]
    assert outcome.action_data["draft_id"] == outcome.draft["draft_id"]


def test_generate_draft_from_opportunity_falls_back_without_gateway():
    outcome = generate_xiaohongshu_draft_from_opportunity(
        {"source_kind": "topic", "title": "巧克力礼盒", "summary": "参与人数: 1万"},
        gateway=None,
        build_prompt=lambda opportunity: "prompt",
    )

    assert "探索" in outcome.draft["title"]
    assert "根据最新侦察结果生成的内容草稿" in outcome.draft["body"]
