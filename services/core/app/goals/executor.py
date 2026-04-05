"""任务执行跟踪器

跟踪任务执行进度，管理任务状态
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta

from app.goals.models import Goal, GoalStatus

logger = logging.getLogger(__name__)


class TaskExecution:
    """任务执行记录"""

    def __init__(
        self,
        goal_id: str,
        started_at: datetime,
        status: GoalStatus = GoalStatus.ACTIVE
    ):
        self.goal_id = goal_id
        self.started_at = started_at
        self.completed_at: Optional[datetime] = None
        self.status = status
        self.progress: float = 0.0  # 0.0 - 1.0
        self.error: Optional[str] = None
        self.metadata: Dict = {}

    def to_dict(self) -> Dict:
        """转换为字典

        Returns:
            字典表示
        """
        return {
            'goal_id': self.goal_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'progress': self.progress,
            'error': self.error,
            'metadata': self.metadata,
        }


class TaskExecutor:
    """任务执行跟踪器

    职责：
    1. 跟踪任务执行状态
    2. 记录执行进度
    3. 处理任务失败
    4. 提供执行统计
    """

    def __init__(self):
        """初始化任务执行跟踪器"""
        self.executions: Dict[str, TaskExecution] = {}
        self.completed_count = 0
        self.failed_count = 0
        self.abandoned_count = 0

    def start_task(self, goal: Goal) -> TaskExecution:
        """开始执行任务

        Args:
            goal: 目标

        Returns:
            任务执行记录
        """
        execution = TaskExecution(
            goal_id=goal.id,
            started_at=datetime.now(timezone.utc),
            status=GoalStatus.ACTIVE
        )

        self.executions[goal.id] = execution
        logger.info(f"开始执行任务：{goal.title} (ID: {goal.id})")

        return execution

    def update_progress(
        self,
        goal_id: str,
        progress: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """更新任务进度

        Args:
            goal_id: 目标ID
            progress: 进度 (0.0 - 1.0)
            metadata: 元数据（可选）
        """
        if goal_id not in self.executions:
            logger.warning(f"任务 {goal_id} 不存在，无法更新进度")
            return

        execution = self.executions[goal_id]
        execution.progress = max(0.0, min(1.0, progress))

        if metadata:
            execution.metadata.update(metadata)

        logger.debug(
            f"任务 {goal_id} 进度更新：{execution.progress * 100:.1f}%"
        )

    def complete_task(
        self,
        goal_id: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """标记任务完成

        Args:
            goal_id: 目标ID
            metadata: 元数据（可选）
        """
        if goal_id not in self.executions:
            logger.warning(f"任务 {goal_id} 不存在，无法标记为完成")
            return

        execution = self.executions[goal_id]
        execution.status = GoalStatus.COMPLETED
        execution.completed_at = datetime.now(timezone.utc)
        execution.progress = 1.0

        if metadata:
            execution.metadata.update(metadata)

        self.completed_count += 1
        logger.info(f"任务 {goal_id} 已完成")

    def fail_task(
        self,
        goal_id: str,
        error: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """标记任务失败

        Args:
            goal_id: 目标ID
            error: 错误信息
            metadata: 元数据（可选）
        """
        if goal_id not in self.executions:
            logger.warning(f"任务 {goal_id} 不存在，无法标记为失败")
            return

        execution = self.executions[goal_id]
        execution.status = GoalStatus.ABANDONED
        execution.completed_at = datetime.now(timezone.utc)
        execution.error = error

        if metadata:
            execution.metadata.update(metadata)

        self.failed_count += 1
        logger.error(f"任务 {goal_id} 失败：{error}")

    def abandon_task(
        self,
        goal_id: str,
        reason: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """放弃任务

        Args:
            goal_id: 目标ID
            reason: 放弃原因
            metadata: 元数据（可选）
        """
        if goal_id not in self.executions:
            logger.warning(f"任务 {goal_id} 不存在，无法放弃")
            return

        execution = self.executions[goal_id]
        execution.status = GoalStatus.ABANDONED
        execution.completed_at = datetime.now(timezone.utc)
        execution.error = reason

        if metadata:
            execution.metadata.update(metadata)

        self.abandoned_count += 1
        logger.warning(f"任务 {goal_id} 已放弃：{reason}")

    def get_execution(self, goal_id: str) -> Optional[TaskExecution]:
        """获取任务执行记录

        Args:
            goal_id: 目标ID

        Returns:
            任务执行记录，如果不存在则返回None
        """
        return self.executions.get(goal_id)

    def get_active_executions(self) -> List[TaskExecution]:
        """获取所有活跃的执行记录

        Returns:
            活跃执行记录列表
        """
        return [
            execution
            for execution in self.executions.values()
            if execution.status == GoalStatus.ACTIVE
        ]

    def get_completed_executions(self) -> List[TaskExecution]:
        """获取所有已完成的执行记录

        Returns:
            已完成执行记录列表
        """
        return [
            execution
            for execution in self.executions.values()
            if execution.status == GoalStatus.COMPLETED
        ]

    def get_failed_executions(self) -> List[TaskExecution]:
        """获取所有失败的执行记录

        Returns:
            失败执行记录列表
        """
        return [
            execution
            for execution in self.executions.values()
            if execution.status == GoalStatus.ABANDONED and execution.error
        ]

    def get_statistics(self) -> Dict:
        """获取执行统计

        Returns:
            统计字典
        """
        total = len(self.executions)
        success_rate = (self.completed_count / total * 100) if total > 0 else 0.0

        return {
            'total_tasks': total,
            'completed': self.completed_count,
            'failed': self.failed_count,
            'abandoned': self.abandoned_count,
            'active': total - self.completed_count - self.failed_count - self.abandoned_count,
            'success_rate': success_rate,
        }

    def cleanup_old_executions(self, days: int = 7) -> int:
        """清理旧的执行记录

        Args:
            days: 保留天数

        Returns:
            清理的数量
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        to_remove = []

        for goal_id, execution in self.executions.items():
            if execution.completed_at and execution.completed_at < cutoff:
                to_remove.append(goal_id)

        for goal_id in to_remove:
            del self.executions[goal_id]

        logger.info(f"清理了 {len(to_remove)} 条旧执行记录")
        return len(to_remove)

    def reset(self) -> None:
        """重置执行跟踪器"""
        self.executions.clear()
        self.completed_count = 0
        self.failed_count = 0
        self.abandoned_count = 0
        logger.info("任务执行跟踪器已重置")
