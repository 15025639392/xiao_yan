import subprocess

from app.usecases import xiaohongshu_chrome_capture as chrome_capture
from app.usecases import xiaohongshu_creator_home_capture as creator_home_capture
from app.usecases.xiaohongshu_lead_capture import extract_lead_capture_from_raw_text
from app.usecases.xiaohongshu_creator_home_capture import extract_creator_home_from_raw_text


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


def test_capture_active_chrome_tab_uses_javascript_when_available(monkeypatch):
    responses = [
        subprocess.CompletedProcess(args=["osascript"], returncode=0, stdout="https://creator.xiaohongshu.com/new/home\n", stderr=""),
        subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="__XIAOYAN_CHROME_CAPTURE__创作服务平台\n小红薯8888\n",
            stderr="",
        ),
    ]

    def fake_run(*args, **kwargs):
        _ = (args, kwargs)
        return responses.pop(0)

    monkeypatch.setattr(chrome_capture.subprocess, "run", fake_run)

    captured = chrome_capture.capture_active_chrome_tab()

    assert captured.url == "https://creator.xiaohongshu.com/new/home"
    assert "创作服务平台" in captured.body_text


def test_capture_active_chrome_tab_falls_back_to_clipboard_when_javascript_disabled(monkeypatch):
    clipboard_writes: list[str] = []
    responses = [
        subprocess.CompletedProcess(args=["osascript"], returncode=0, stdout="https://creator.xiaohongshu.com/new/home\n", stderr=""),
        subprocess.CompletedProcess(
            args=["osascript"],
            returncode=1,
            stdout="",
            stderr="execution error: 通过 AppleScript 执行 JavaScript 的功能已关闭。",
        ),
        subprocess.CompletedProcess(args=["pbpaste"], returncode=0, stdout="original clipboard", stderr=""),
        subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="__XIAOYAN_CHROME_COPY_DONE__\n",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=["pbpaste"],
            returncode=0,
            stdout="创作服务平台\n小红薯9999\n#低成本副业\n12万人参与，3亿次浏览\n",
            stderr="",
        ),
        subprocess.CompletedProcess(args=["pbcopy"], returncode=0, stdout="", stderr=""),
    ]

    def fake_run(cmd, *args, **kwargs):
        _ = args
        result = responses.pop(0)
        if cmd == ["pbcopy"]:
            clipboard_writes.append(kwargs.get("input", ""))
        return result

    monkeypatch.setattr(chrome_capture.subprocess, "run", fake_run)

    captured = chrome_capture.capture_active_chrome_tab()

    assert captured.url == "https://creator.xiaohongshu.com/new/home"
    assert "#低成本副业" in captured.body_text
    assert clipboard_writes == ["original clipboard"]


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
