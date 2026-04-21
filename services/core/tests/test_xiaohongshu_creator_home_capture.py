from app.usecases import xiaohongshu_creator_home_capture as creator_home_capture
from app.usecases import xiaohongshu_lead_capture as lead_capture
from app.usecases.xiaohongshu_creator_home_capture import extract_creator_home_from_raw_text
from app.usecases.xiaohongshu_lead_capture import extract_lead_capture_from_raw_text


def test_extract_creator_home_from_raw_text_pulls_account_topics_and_activities():
    result = extract_creator_home_from_raw_text(
        """
创作服务平台
小红薯66661C17
创作话题
#高颜值巧克力
30万人参与，14.4亿次浏览
#早餐吃什么
288.7万人参与，105.3亿次浏览
热门活动
官方活动, 奖励多多
RED新生代创作大赛 03-30 至 05-10
春天见面会 04-18 至 04-30
"""
    )

    assert result.account_name == "小红薯66661C17"
    assert [item.topic for item in result.topics] == ["#高颜值巧克力", "#早餐吃什么"]
    assert result.topics[0].view_count == "14.4亿次浏览"
    assert [item.title for item in result.activities] == ["RED新生代创作大赛", "春天见面会"]
    assert result.activities[0].incentive_hint == "官方活动, 奖励多多"


def test_extract_creator_home_from_raw_text_handles_split_activity_dates_and_skips_stat_range():
    result = extract_creator_home_from_raw_text(
        """
创作服务平台
统计周期 04-11 至 04-17
热门活动
官方活动, 奖励多多
RED新生代创作大赛
03-30 至 05-10
我的时尚缪斯
04-19 至 05-31
"""
    )

    assert [item.title for item in result.activities] == ["RED新生代创作大赛", "我的时尚缪斯"]
    assert result.activities[0].date_range == "03-30 至 05-10"


def test_capture_creator_home_via_browser_organ_reads_snapshot_and_closes_session(monkeypatch):
    calls: list[str] = []

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        calls.append(capability)
        if capability == "browser.open":
            return {"session_id": "xhs-session", "resolved_url": "https://creator.xiaohongshu.com/new/home"}
        if capability == "browser.snapshot":
            return {
                "url": "https://creator.xiaohongshu.com/new/home",
                "text_content": "创作服务平台\n小红薯8888\n#低成本副业\n12万人参与，3亿次浏览\n",
            }
        if capability == "browser.close":
            return {"session_id": args["session_id"], "status": "closed"}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(creator_home_capture, "call_browser_capability", fake_call_browser_capability)

    captured = creator_home_capture.capture_xiaohongshu_creator_home_via_browser_organ()

    assert captured.source_url == "https://creator.xiaohongshu.com/new/home"
    assert captured.account_name == "小红薯8888"
    assert calls == ["browser.open", "browser.snapshot", "browser.close"]


def test_capture_lead_signals_via_browser_organ_uses_existing_session(monkeypatch):
    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = (args, timeout_seconds)
        if capability == "browser.snapshot":
            return {
                "url": "https://www.xiaohongshu.com/explore/test",
                "text_content": "爆款起号模板复盘\n点赞 128\n收藏 46\n评论 12\n分享 3\n想加微信细聊预算和报价\n",
            }
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(lead_capture, "call_browser_capability", fake_call_browser_capability)

    captured = lead_capture.capture_xiaohongshu_lead_signals_via_browser_organ(
        session_id="browser-session",
        title_hint="爆款起号模板复盘",
    )

    assert captured.source_url == "https://www.xiaohongshu.com/explore/test"
    assert captured.like_count == "128"
    assert captured.wechat_signal_count == 1


def test_extract_lead_capture_from_raw_text_pulls_metrics_and_high_intent_lines():
    result = extract_lead_capture_from_raw_text(
        """
爆款起号模板复盘
点赞 128
收藏 46
评论 12
分享 3
这个怎么做，适合我这种新手吗？
可以私信我一版方案吗？
想加微信细聊预算和报价
""",
        title_hint="爆款起号模板复盘",
    )

    assert result.note_title == "爆款起号模板复盘"
    assert result.like_count == "128"
    assert result.collect_count == "46"
    assert result.comment_count == "12"
    assert result.share_count == "3"
    assert result.direct_message_signal_count == 1
    assert result.wechat_signal_count == 1
    assert result.purchase_signal_count >= 1
    assert any("怎么" == keyword for keyword in result.lead_keywords)
    assert any("微信" in line for line in result.matched_comment_lines)
    assert "导到微信人数：1" in result.tracking_template
