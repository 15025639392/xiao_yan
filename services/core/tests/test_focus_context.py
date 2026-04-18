from app.domain.models import BeingState, TodayPlan, TodayPlanStep, TodayPlanStepStatus, WakeMode
from app.focus.context import build_focus_context
from app.goals.models import Goal, GoalAdmissionMeta
from app.goals.repository import InMemoryGoalRepository


def test_focus_context_describes_user_topic_plan_focus():
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(
        Goal(
            id="goal-1",
            title="整理今天的对话记忆",
            source="你现在在忙什么",
            admission=GoalAdmissionMeta(
                score=0.82,
                recommended_decision="admit",
                applied_decision="admit",
                reason="user_score",
            ),
        )
    )
    state = BeingState(
        mode=WakeMode.AWAKE,
        active_goal_ids=[goal.id],
        today_plan=TodayPlan(
            goal_id=goal.id,
            goal_title=goal.title,
            steps=[
                TodayPlanStep(content="回看昨天的对话", status=TodayPlanStepStatus.PENDING),
                TodayPlanStep(content="整理关键线索", status=TodayPlanStepStatus.PENDING),
            ],
        ),
    )

    focus_context = build_focus_context(state=state, goal_repository=goal_repository)

    assert focus_context is not None
    assert focus_context.goal_title == "整理今天的对话记忆"
    assert focus_context.source_kind == "user_topic_goal"
    assert focus_context.source_label == "刚接住你这轮话题的事"
    assert focus_context.reason_kind == "today_plan_pending"
    assert focus_context.reason_label == "今天这条还剩 2 步没做完"


def test_focus_context_describes_late_chain_focus_without_today_plan():
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(
        Goal(
            id="goal-1",
            title="继续推进：继续推进：整理今天的对话记忆",
            chain_id="chain-1",
            generation=2,
        )
    )
    state = BeingState(
        mode=WakeMode.AWAKE,
        active_goal_ids=[goal.id],
    )

    focus_context = build_focus_context(state=state, goal_repository=goal_repository)

    assert focus_context is not None
    assert focus_context.source_kind == "goal_chain"
    assert focus_context.source_label == "她一直接着往下推进的这条线"
    assert focus_context.reason_kind == "goal_chain_closing"
    assert focus_context.reason_label == "这条线已经推到第3步了，现在主要是在收尾"


def test_focus_context_can_fall_back_to_today_plan_when_goal_missing():
    goal_repository = InMemoryGoalRepository()
    state = BeingState(
        mode=WakeMode.AWAKE,
        active_goal_ids=["missing-goal"],
        today_plan=TodayPlan(
            goal_id="missing-goal",
            goal_title="收住今天这条线",
            steps=[
                TodayPlanStep(content="回看今天发生了什么", status=TodayPlanStepStatus.COMPLETED),
                TodayPlanStep(content="决定是否继续推进", status=TodayPlanStepStatus.COMPLETED),
            ],
        ),
    )

    focus_context = build_focus_context(state=state, goal_repository=goal_repository)

    assert focus_context is not None
    assert focus_context.goal_title == "收住今天这条线"
    assert focus_context.source_kind == "today_plan_fallback"
    assert focus_context.source_label == "今天这条还接着在延续的计划"
    assert focus_context.reason_kind == "today_plan_warm_closure"
    assert focus_context.reason_label == "今天这条刚做完，但那股收尾的劲还在"
