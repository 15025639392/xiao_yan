from datetime import datetime, timezone

from app.focus.selection import select_focus_goal
from app.goals.models import Goal


def test_select_focus_goal_prefers_latest_chain_when_recent_autobio_exists():
    ordinary_goal = Goal(
        id="goal-ordinary",
        title="整理今天的桌面文件",
        created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
    )
    chain_goal = Goal(
        id="goal-chain",
        title="继续推进：继续推进：整理今天的对话记忆",
        chain_id="chain-1",
        generation=2,
        created_at=datetime(2026, 4, 5, 0, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 5, 0, 2, tzinfo=timezone.utc),
    )

    selected = select_focus_goal(
        [ordinary_goal, chain_goal],
        recent_autobio="我最近像是一路从第1步走到第3步。",
    )

    assert selected is not None
    assert selected.id == "goal-chain"


def test_select_focus_goal_respects_preferred_goal_order_when_switching_focus():
    first_goal = Goal(id="goal-1", title="先前的主目标")
    second_goal = Goal(id="goal-2", title="接替焦点的目标")

    selected = select_focus_goal(
        [first_goal, second_goal],
        preferred_goal_ids=["goal-2", "goal-1"],
    )

    assert selected is not None
    assert selected.id == "goal-2"
