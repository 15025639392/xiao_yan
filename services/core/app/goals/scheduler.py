"""智能任务调度器

根据优先级、依赖关系和资源情况进行任务调度
"""

import logging
from typing import List, Optional, Set, Dict
from datetime import datetime, timezone, timedelta

from app.goals.models import Goal, GoalStatus

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度器

    职责：
    1. 根据优先级排序任务
    2. 考虑任务依赖关系
    3. 控制并发执行数量
    4. 生成可执行任务队列
    """

    def __init__(self, max_concurrent: int = 3):
        """初始化任务调度器

        Args:
            max_concurrent: 最大并发任务数
        """
        self.max_concurrent = max_concurrent
        self.current_running: Set[str] = set()

    def schedule_tasks(
        self,
        all_goals: List[Goal],
        max_concurrent: Optional[int] = None
    ) -> List[Goal]:
        """调度任务，返回应该执行的任务列表

        Args:
            all_goals: 所有目标列表
            max_concurrent: 最大并发数（可选，默认使用初始化时的值）

        Returns:
            可执行的任务列表
        """
        if max_concurrent is not None:
            self.max_concurrent = max_concurrent

        # 1. 过滤可执行任务
        executable_tasks = self._filter_executable(all_goals)

        # 2. 按优先级排序
        prioritized_tasks = self._prioritize_tasks(executable_tasks)

        # 3. 考虑依赖关系
        dependency_ordered = self._resolve_dependencies(prioritized_tasks, all_goals)

        # 4. 考虑并发限制
        scheduled = self._apply_concurrency_limit(dependency_ordered)

        # 5. 更新运行中的任务
        self.current_running = {task.id for task in scheduled}

        logger.info(
            f"调度完成：从 {len(all_goals)} 个任务中选择了 {len(scheduled)} 个任务执行"
        )

        return scheduled

    def _filter_executable(self, goals: List[Goal]) -> List[Goal]:
        """过滤可执行的任务

        Args:
            goals: 所有目标

        Returns:
            可执行的目标列表
        """
        executable = []

        for goal in goals:
            # 只选择活跃状态的任务
            if goal.status != GoalStatus.ACTIVE:
                continue

            # 排除已经在运行的任务
            if goal.id in self.current_running:
                continue

            # 排除子目标（父目标未完成时）
            if goal.parent_goal_id and not self._is_parent_completed(goal, goals):
                continue

            executable.append(goal)

        return executable

    def _is_parent_completed(self, goal: Goal, all_goals: List[Goal]) -> bool:
        """检查父目标是否已完成

        Args:
            goal: 子目标
            all_goals: 所有目标

        Returns:
            父目标是否已完成
        """
        if not goal.parent_goal_id:
            return True

        for g in all_goals:
            if g.id == goal.parent_goal_id:
                return g.status == GoalStatus.COMPLETED

        # 如果找不到父目标，假设已完成
        return True

    def _prioritize_tasks(self, goals: List[Goal]) -> List[Goal]:
        """按优先级对任务排序

        Args:
            goals: 目标列表

        Returns:
            排序后的目标列表
        """
        def priority_score(goal: Goal) -> float:
            score = 0.0

            # 1. 越早创建的优先级越高
            age_days = (datetime.now(timezone.utc) - goal.created_at).total_seconds() / 86400
            score += age_days * 0.1

            # 2. 代数越低（越顶层）优先级越高
            score -= goal.generation * 2.0

            # 3. 有来源的目标优先级更高
            if goal.source:
                score += 1.0

            # 4. 有父目标的优先级略低（因为需要先完成父目标）
            if goal.parent_goal_id:
                score -= 0.5

            return score

        # 按分数降序排序（分数越高优先级越高）
        return sorted(goals, key=priority_score, reverse=True)

    def _resolve_dependencies(
        self,
        goals: List[Goal],
        all_goals: List[Goal]
    ) -> List[Goal]:
        """解决任务依赖关系

        Args:
            goals: 已排序的任务列表
            all_goals: 所有任务

        Returns:
            考虑依赖后的任务列表
        """
        # 构建依赖图
        dependency_map: Dict[str, List[str]] = {}
        for goal in goals:
            if goal.parent_goal_id:
                dependency_map[goal.id] = [goal.parent_goal_id]

        # 拓扑排序（简化版）
        # 实际实现可能需要更复杂的依赖解析
        ordered = []

        for goal in goals:
            # 检查所有父目标是否完成
            if not goal.parent_goal_id:
                ordered.append(goal)
            elif self._is_parent_completed(goal, all_goals):
                ordered.append(goal)

        return ordered

    def _apply_concurrency_limit(self, goals: List[Goal]) -> List[Goal]:
        """应用并发限制

        Args:
            goals: 任务列表

        Returns:
            限制数量后的任务列表
        """
        return goals[:self.max_concurrent]

    def mark_task_completed(self, task_id: str) -> None:
        """标记任务完成

        Args:
            task_id: 任务ID
        """
        if task_id in self.current_running:
            self.current_running.remove(task_id)
            logger.info(f"任务 {task_id} 已完成，从运行队列中移除")

    def mark_task_failed(self, task_id: str) -> None:
        """标记任务失败

        Args:
            task_id: 任务ID
        """
        if task_id in self.current_running:
            self.current_running.remove(task_id)
            logger.warning(f"任务 {task_id} 失败，从运行队列中移除")

    def get_running_tasks_count(self) -> int:
        """获取当前运行的任务数

        Returns:
            运行中的任务数
        """
        return len(self.current_running)

    def can_add_task(self) -> bool:
        """检查是否可以添加新任务

        Returns:
            是否可以添加
        """
        return len(self.current_running) < self.max_concurrent

    def reset(self) -> None:
        """重置调度器状态"""
        self.current_running.clear()
        logger.info("任务调度器已重置")

    def get_schedule_status(self) -> Dict:
        """获取调度状态

        Returns:
            调度状态字典
        """
        return {
            'max_concurrent': self.max_concurrent,
            'current_running': len(self.current_running),
            'available_slots': self.max_concurrent - len(self.current_running),
            'running_task_ids': list(self.current_running),
        }
