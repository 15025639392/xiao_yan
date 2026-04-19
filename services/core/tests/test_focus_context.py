from app.domain.models import BeingState, WakeMode
from app.focus.context import build_focus_context


def test_focus_context_describes_focus_trace():
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "focus_trace",
            "title": "整理今天的对话记忆",
            "why_now": "这条线还挂在眼前，因为今天这条还剩 2 步没做完。",
        },
    )

    focus_context = build_focus_context(state=state)

    assert focus_context is not None
    assert focus_context.focus_title == "整理今天的对话记忆"
    assert focus_context.source_kind == "focus_trace"
    assert focus_context.source_label == "一条挂在手上、但不等于目标本身的推进线索"
    assert focus_context.reason_kind == "focus_subject_reason"
    assert "今天这条还剩 2 步没做完" in focus_context.reason_label


def test_focus_context_describes_late_focus_trace():
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "focus_trace",
            "title": "继续推进：继续推进：整理今天的对话记忆",
            "why_now": "这条线已经推到第3步了，现在主要是在收尾。",
        },
    )

    focus_context = build_focus_context(state=state)

    assert focus_context is not None
    assert focus_context.source_kind == "focus_trace"
    assert focus_context.source_label == "一条挂在手上、但不等于目标本身的推进线索"
    assert focus_context.reason_kind == "focus_subject_reason"
    assert focus_context.reason_label == "这条线已经推到第3步了，现在主要是在收尾。"

def test_focus_context_prefers_focus_subject_for_user_topic_lingering():
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "user_topic",
            "title": "你刚才说最近提不起劲",
            "why_now": "你刚才提到这件事，但现在还没到把它正式推进成目标的时候。",
            "source_ref": "我最近挺累的，感觉做什么都提不起劲",
        },
    )

    focus_context = build_focus_context(state=state)

    assert focus_context is not None
    assert focus_context.focus_title == "你刚才说最近提不起劲"
    assert focus_context.source_kind == "user_topic_focus"
    assert focus_context.reason_kind == "user_topic_lingering"
    assert "还没到把它正式推进成目标" in focus_context.reason_label


def test_focus_context_does_not_auto_derive_without_focus_subject():
    state = BeingState(mode=WakeMode.AWAKE)

    focus_context = build_focus_context(state=state)

    assert focus_context is None
