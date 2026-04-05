"""目标管理测试

测试目标分解器、任务调度器和执行跟踪器
"""

import pytest
from datetime import datetime, timezone

from app.goals.models import Goal, GoalStatus
from app.goals.decomposer import GoalDecomposer
from app.goals.scheduler import TaskScheduler
from app.goals.executor import TaskExecutor, TaskExecution


# ==================== GoalDecomposer Tests ====================

def test_decomposer_initialization():
    """测试分解器初始化"""
    decomposer = GoalDecomposer()
    assert decomposer.llm_gateway is None

    decomposer_with_llm = GoalDecomposer(llm_gateway="mock-gateway")
    assert decomposer_with_llm.llm_gateway == "mock-gateway"


def test_simple_decompose():
    """测试简单分解策略"""
    decomposer = GoalDecomposer()

    parent_goal = Goal(
        title="学习Python编程",
        source="自我提升",
    )

    subgoals = decomposer._simple_decompose(parent_goal, max_subtasks=3)

    # 验证
    assert len(subgoals) == 3
    assert all(goal.parent_goal_id == parent_goal.id for goal in subgoals)
    assert all(goal.generation == 1 for goal in subgoals)
    assert subgoals[0].title.startswith("分析")
    assert subgoals[1].title.startswith("规划")


def test_estimate_complexity():
    """测试复杂度评估"""
    decomposer = GoalDecomposer()

    # 简单目标
    simple_goal = Goal(title="买咖啡")
    simple_complexity = decomposer.estimate_complexity(simple_goal)
    assert simple_complexity['level'] == "简单"

    # 复杂目标
    complex_goal = Goal(
        title="创建一个复杂的机器学习模型来分析大规模数据集并进行预测",
        source="项目需求",
        generation=2,
    )
    complex_complexity = decomposer.estimate_complexity(complex_goal)
    assert complex_complexity['level'] in ["中等", "复杂"]


def test_should_decompose():
    """测试是否需要分解"""
    decomposer = GoalDecomposer()

    simple_goal = Goal(title="买咖啡")
    assert not decomposer.should_decompose(simple_goal, threshold=1.0)

    complex_goal = Goal(
        title="创建一个复杂的机器学习模型来分析大规模数据集",
        source="项目",
    )
    assert decomposer.should_decompose(complex_goal, threshold=1.0)


def test_prioritize_subtasks():
    """测试子任务优先级"""
    decomposer = GoalDecomposer()

    parent_goal = Goal(title="学习Python")
    subtasks = [
        Goal(title="子任务1", parent_goal_id=parent_goal.id, generation=1),
        Goal(title="子任务2", parent_goal_id=parent_goal.id, generation=1),
        Goal(title="子任务3", parent_goal_id=parent_goal.id, generation=1),
    ]

    # 添加创建时间差异
    import time
    time.sleep(0.01)
    subtasks[1].created_at = datetime.now(timezone.utc)
    time.sleep(0.01)
    subtasks[2].created_at = datetime.now(timezone.utc)

    prioritized = decomposer.prioritize_subtasks(subtasks, parent_goal)

    # 验证返回了所有子任务
    assert len(prioritized) == 3


# ==================== TaskScheduler Tests ====================

def test_scheduler_initialization():
    """测试调度器初始化"""
    scheduler = TaskScheduler(max_concurrent=5)
    assert scheduler.max_concurrent == 5
    assert len(scheduler.current_running) == 0


def test_schedule_tasks():
    """测试任务调度"""
    scheduler = TaskScheduler(max_concurrent=2)

    goals = [
        Goal(id="1", title="任务1", status=GoalStatus.ACTIVE),
        Goal(id="2", title="任务2", status=GoalStatus.ACTIVE),
        Goal(id="3", title="任务3", status=GoalStatus.ACTIVE),
        Goal(id="4", title="任务4", status=GoalStatus.COMPLETED),
    ]

    scheduled = scheduler.schedule_tasks(goals)

    # 验证只选择活跃任务
    assert all(goal.status == GoalStatus.ACTIVE for goal in scheduled)
    # 验证并发限制
    assert len(scheduled) <= 2


def test_filter_executable():
    """测试过滤可执行任务"""
    scheduler = TaskScheduler()

    goals = [
        Goal(id="1", title="活跃任务", status=GoalStatus.ACTIVE),
        Goal(id="2", title="已完成任务", status=GoalStatus.COMPLETED),
        Goal(id="3", title="暂停任务", status=GoalStatus.PAUSED),
    ]

    executable = scheduler._filter_executable(goals)

    # 验证只返回活跃任务
    assert len(executable) == 1
    assert executable[0].id == "1"


def test_prioritize_tasks():
    """测试任务优先级"""
    scheduler = TaskScheduler()

    goals = [
        Goal(
            id="1",
            title="顶层任务",
            status=GoalStatus.ACTIVE,
            generation=0,
            created_at=datetime.now(timezone.utc)
        ),
        Goal(
            id="2",
            title="子任务",
            status=GoalStatus.ACTIVE,
            generation=1,
            parent_goal_id="1",
            created_at=datetime.now(timezone.utc)
        ),
        Goal(
            id="3",
            title="有来源的任务",
            status=GoalStatus.ACTIVE,
            source="重要",
            generation=0,
            created_at=datetime.now(timezone.utc)
        ),
    ]

    prioritized = scheduler._prioritize_tasks(goals)

    # 验证所有任务都被包含
    assert len(prioritized) == 3


def test_apply_concurrency_limit():
    """测试并发限制"""
    scheduler = TaskScheduler(max_concurrent=2)

    goals = [
        Goal(id=f"{i}", title=f"任务{i}") for i in range(5)
    ]

    limited = scheduler._apply_concurrency_limit(goals)

    # 验证数量限制
    assert len(limited) == 2


def test_mark_task_completed():
    """测试标记任务完成"""
    scheduler = TaskScheduler()

    # 添加到运行队列
    scheduler.current_running.add("task1")

    # 标记完成
    scheduler.mark_task_completed("task1")

    # 验证已移除
    assert "task1" not in scheduler.current_running


def test_can_add_task():
    """测试是否可以添加任务"""
    scheduler = TaskScheduler(max_concurrent=3)

    # 初始状态
    assert scheduler.can_add_task()

    # 添加两个任务
    scheduler.current_running.add("task1")
    scheduler.current_running.add("task2")
    assert scheduler.can_add_task()

    # 添加第三个任务
    scheduler.current_running.add("task3")
    assert not scheduler.can_add_task()


def test_get_schedule_status():
    """测试获取调度状态"""
    scheduler = TaskScheduler(max_concurrent=3)
    scheduler.current_running.add("task1")
    scheduler.current_running.add("task2")

    status = scheduler.get_schedule_status()

    # 验证状态
    assert status['max_concurrent'] == 3
    assert status['current_running'] == 2
    assert status['available_slots'] == 1
    assert set(status['running_task_ids']) == {"task1", "task2"}


def test_reset_scheduler():
    """测试重置调度器"""
    scheduler = TaskScheduler()
    scheduler.current_running.add("task1")
    scheduler.current_running.add("task2")

    scheduler.reset()

    # 验证已重置
    assert len(scheduler.current_running) == 0


# ==================== TaskExecutor Tests ====================

def test_executor_initialization():
    """测试执行器初始化"""
    executor = TaskExecutor()

    assert executor.executions == {}
    assert executor.completed_count == 0
    assert executor.failed_count == 0
    assert executor.abandoned_count == 0


def test_start_task():
    """测试开始任务"""
    executor = TaskExecutor()

    goal = Goal(id="task1", title="测试任务")

    execution = executor.start_task(goal)

    # 验证执行记录
    assert execution.goal_id == "task1"
    assert execution.status == GoalStatus.ACTIVE
    assert execution.progress == 0.0
    assert "task1" in executor.executions


def test_update_progress():
    """测试更新进度"""
    executor = TaskExecutor()

    goal = Goal(id="task1", title="测试任务")
    executor.start_task(goal)

    # 更新进度
    executor.update_progress("task1", 0.5, metadata={"step": "中间步骤"})

    execution = executor.get_execution("task1")
    assert execution.progress == 0.5
    assert execution.metadata["step"] == "中间步骤"


def test_complete_task():
    """测试完成任务"""
    executor = TaskExecutor()

    goal = Goal(id="task1", title="测试任务")
    executor.start_task(goal)

    # 完成任务
    executor.complete_task("task1", metadata={"result": "成功"})

    execution = executor.get_execution("task1")
    assert execution.status == GoalStatus.COMPLETED
    assert execution.progress == 1.0
    assert execution.completed_at is not None
    assert executor.completed_count == 1


def test_fail_task():
    """测试任务失败"""
    executor = TaskExecutor()

    goal = Goal(id="task1", title="测试任务")
    executor.start_task(goal)

    # 标记失败
    executor.fail_task("task1", error="网络错误")

    execution = executor.get_execution("task1")
    assert execution.status == GoalStatus.ABANDONED
    assert execution.error == "网络错误"
    assert executor.failed_count == 1


def test_abandon_task():
    """测试放弃任务"""
    executor = TaskExecutor()

    goal = Goal(id="task1", title="测试任务")
    executor.start_task(goal)

    # 放弃任务
    executor.abandon_task("task1", reason="不再需要")

    execution = executor.get_execution("task1")
    assert execution.status == GoalStatus.ABANDONED
    assert execution.error == "不再需要"
    assert executor.abandoned_count == 1


def test_get_active_executions():
    """测试获取活跃执行"""
    executor = TaskExecutor()

    goal1 = Goal(id="task1", title="任务1")
    goal2 = Goal(id="task2", title="任务2")
    goal3 = Goal(id="task3", title="任务3")

    executor.start_task(goal1)
    executor.start_task(goal2)
    executor.start_task(goal3)

    # 完成一个任务
    executor.complete_task("task2")

    active = executor.get_active_executions()

    # 验证返回活跃任务
    assert len(active) == 2
    active_ids = {e.goal_id for e in active}
    assert active_ids == {"task1", "task3"}


def test_get_statistics():
    """测试获取统计信息"""
    executor = TaskExecutor()

    # 创建任务
    for i in range(5):
        executor.start_task(Goal(id=f"task{i}", title=f"任务{i}"))

    # 完成一些任务
    executor.complete_task("task0")
    executor.complete_task("task1")

    # 失败一些任务
    executor.fail_task("task2", error="错误1")

    # 放弃一些任务
    executor.abandon_task("task3", reason="不需要")

    stats = executor.get_statistics()

    # 验证统计
    assert stats['total_tasks'] == 5
    assert stats['completed'] == 2
    assert stats['failed'] == 1
    assert stats['abandoned'] == 1
    assert stats['active'] == 1
    assert stats['success_rate'] == 40.0


def test_reset_executor():
    """测试重置执行器"""
    executor = TaskExecutor()

    goal = Goal(id="task1", title="测试任务")
    executor.start_task(goal)

    executor.reset()

    # 验证已重置
    assert len(executor.executions) == 0
    assert executor.completed_count == 0
    assert executor.failed_count == 0
    assert executor.abandoned_count == 0
