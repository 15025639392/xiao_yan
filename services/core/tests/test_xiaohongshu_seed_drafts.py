from app.api.platform_route_models import XiaohongshuCreatorHomePreviewRequest
from app.usecases.xiaohongshu_creator_home_preview import build_xiaohongshu_creator_home_preview_items
from app.usecases.xiaohongshu_seed_drafts import build_seed_drafts_from_creator_opportunities


def test_build_seed_drafts_from_creator_opportunities():
    opportunities = build_xiaohongshu_creator_home_preview_items(
        XiaohongshuCreatorHomePreviewRequest(
            account_name="小红薯66661C17",
            topics=[{"topic": "#早餐吃什么"}],
            activities=[{"title": "RED新生代创作大赛"}],
        )
    )

    drafts = build_seed_drafts_from_creator_opportunities(opportunities)

    assert len(drafts) == 2
    assert drafts[0].source_kind == "topic"
    assert "#早餐吃什么" in drafts[0].draft_title
    assert "情绪和关系瞬间" in drafts[0].opening
    assert drafts[1].source_kind == "activity"
    assert "RED新生代创作大赛" in drafts[1].opening
    assert "小晏可以继续陪你慢慢看" in drafts[1].body_points[2]
