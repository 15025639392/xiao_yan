from __future__ import annotations

from pydantic import BaseModel, Field

from app.usecases.xiaohongshu_creator_home_preview import XiaohongshuCreatorOpportunityItem


class XiaohongshuSeedDraft(BaseModel):
    source_kind: str
    source_title: str
    draft_title: str
    opening: str
    body_points: list[str] = Field(default_factory=list)
    closing_cta: str


def build_seed_drafts_from_creator_opportunities(
    items: list[XiaohongshuCreatorOpportunityItem],
) -> list[XiaohongshuSeedDraft]:
    return [_build_seed_draft(item) for item in items]


def _build_seed_draft(item: XiaohongshuCreatorOpportunityItem) -> XiaohongshuSeedDraft:
    if item.source_kind == "activity":
        return XiaohongshuSeedDraft(
            source_kind=item.source_kind,
            source_title=item.title,
            draft_title=f"{item.title} 这个活动，小晏会把它写成什么样的轻科普内容？",
            opening=f"刚看到 {item.title}，我第一反应不是追活动热闹，而是想：它背后有没有一个能被用户立刻代入的情绪或关系场景。",
            body_points=[
                "先从一个会让人觉得“这就是我”的具体瞬间切入，不要一上来介绍活动规则。",
                "正文只拆一个情绪、关系或自我认知角度，用人话解释，保留“小晏在理解你”的口吻。",
                "结尾留一个低压力互动口子，比如“如果你也有过这种时刻，小晏可以继续陪你慢慢看”。",
            ],
            closing_cta="如果你愿意，我可以继续把这次活动拆成更具体的封面标题和卡片页文案。",
        )
    return XiaohongshuSeedDraft(
        source_kind=item.source_kind,
        source_title=item.title,
        draft_title=f"{item.title} 这个话题，小晏会先从哪个被忽略的瞬间讲起？",
        opening=f"看到 {item.title} 这个话题后，我没有先想怎么蹭热度，而是先想：这个话题背后，用户最容易说不清的情绪和关系瞬间是什么。",
        body_points=[
            "先从一个具体场景切入，让读者一眼感觉“这就是我”，不要先讲概念。",
            "中段只拆一个情绪、关系或自我认知角度，让内容有轻科普价值，但读起来像被理解。",
            "结尾留一个收藏或评论理由，比如“如果你也经历过，小晏可以继续陪你慢慢看清这件事”。",
        ],
        closing_cta="如果这类内容你也想继续看，我下一篇就把它拆成更适合发图卡的版本。",
    )
