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
            draft_title=f"{item.title}值得跟吗？我会用这套低成本起号法先试一轮",
            opening=f"刚看到 {item.title}，第一反应不是冲热闹，而是想它能不能帮新号更快拿到第一波真实反馈。",
            body_points=[
                "先不追求爆款，先做一条能让人看懂你在解决什么问题的内容。",
                "正文只讲一个具体场景，一个具体做法，一个具体结果，避免写成空泛口号。",
                "评论区留一个低压力互动口子，比如“想看我拆解这套选题框架，可以留言”。",
            ],
            closing_cta="如果你也在做小红书冷启动，我可以继续把这次活动拆成更具体的发文模板。",
        )
    return XiaohongshuSeedDraft(
        source_kind=item.source_kind,
        source_title=item.title,
        draft_title=f"{item.title}能不能带来流量？我会这样把热点写成可转化内容",
        opening=f"看到 {item.title} 这个话题后，我没有先想怎么蹭热度，而是先想怎么把流量变成后续可承接的咨询和互动。",
        body_points=[
            "先从一个真实问题切入，让读者知道这篇内容到底在帮谁解决什么事。",
            "中段给出 3 个可执行步骤，内容要让人能立刻照着做，而不是只看完觉得有道理。",
            "结尾埋一个轻量转化动作，比如“需要我整理成清单版，可以留言拿模板”。",
        ],
        closing_cta="如果这类内容你也想继续看，我下一篇就把具体模板直接展开。",
    )
