"""任务分解器

将复杂目标分解为可执行的子任务
"""

import json
import logging
from typing import List, Optional

from app.goals.models import Goal, GoalStatus
from app.llm.schemas import ChatMessage

logger = logging.getLogger(__name__)


class GoalDecomposer:
    """任务分解器

    职责：
    1. 将复杂目标分解为可执行的子任务
    2. 评估目标复杂度
    3. 生成子任务的优先级
    """

    def __init__(self, llm_gateway=None):
        """初始化任务分解器

        Args:
            llm_gateway: LLM网关（可选）
        """
        self.llm_gateway = llm_gateway

    async def decompose_goal(
        self,
        parent_goal: Goal,
        max_subtasks: int = 5
    ) -> List[Goal]:
        """分解目标为子目标

        Args:
            parent_goal: 父目标
            max_subtasks: 最大子任务数量

        Returns:
            子目标列表
        """
        if not self.llm_gateway:
            # 如果没有LLM网关，使用简单的分解策略
            return self._simple_decompose(parent_goal, max_subtasks)

        # 使用LLM进行智能分解
        return await self._llm_decompose(parent_goal, max_subtasks)

    async def _llm_decompose(
        self,
        parent_goal: Goal,
        max_subtasks: int
    ) -> List[Goal]:
        """使用LLM分解目标

        Args:
            parent_goal: 父目标
            max_subtasks: 最大子任务数量

        Returns:
            子目标列表
        """
        prompt = f"""
请将以下目标分解为可执行的子任务列表：

目标：{parent_goal.title}
来源：{parent_goal.source or '无'}
描述：{parent_goal.source or '请根据目标标题制定执行计划'}

要求：
1. 每个子任务都是具体的、可执行的
2. 子任务之间有合理的顺序
3. 子任务数量不超过{max_subtasks}个
4. 每个子任务包含标题和简要描述

请以JSON数组格式返回，每个元素包含title和source字段。
"""

        try:
            messages = [ChatMessage(role="user", content=prompt)]
            result = await self.llm_gateway.chat_async(messages)
            subtasks_data = json.loads(result)

            subgoals = []
            for i, task_data in enumerate(subtasks_data):
                subgoal = Goal(
                    title=task_data.get('title', f"子任务 {i+1}"),
                    source=task_data.get('source', ''),
                    parent_goal_id=parent_goal.id,
                    generation=parent_goal.generation + 1,
                    status=GoalStatus.ACTIVE,
                )
                subgoals.append(subgoal)

            logger.info(
                f"成功将目标 '{parent_goal.title}' 分解为 {len(subgoals)} 个子任务"
            )
            return subgoals
        except Exception as e:
            logger.error(f"任务分解失败：{e}")
            # 降级到简单分解
            return self._simple_decompose(parent_goal, max_subtasks)

    def _simple_decompose(
        self,
        parent_goal: Goal,
        max_subtasks: int
    ) -> List[Goal]:
        """简单分解策略（无LLM）

        Args:
            parent_goal: 父目标
            max_subtasks: 最大子任务数量

        Returns:
            子目标列表
        """
        # 基于目标标题生成简单的子任务
        subtasks = []
        common_patterns = [
            "分析",
            "规划",
            "准备",
            "执行",
            "验证",
            "优化",
            "总结",
        ]

        for i in range(min(max_subtasks, len(common_patterns))):
            subtask = Goal(
                title=f"{common_patterns[i]} {parent_goal.title}",
                source=f"自动分解自 {parent_goal.title}",
                parent_goal_id=parent_goal.id,
                generation=parent_goal.generation + 1,
                status=GoalStatus.ACTIVE,
            )
            subtasks.append(subtask)

        logger.info(
            f"使用简单策略将目标 '{parent_goal.title}' 分解为 {len(subtasks)} 个子任务"
        )
        return subtasks

    def estimate_complexity(self, goal: Goal) -> dict:
        """评估目标复杂度

        Args:
            goal: 目标

        Returns:
            复杂度评估结果，包含 level, score, factors
        """
        # 基于多个维度评估
        factors = {
            'title_length': len(goal.title),
            'has_source': bool(goal.source),
            'has_parent': bool(goal.parent_goal_id),
            'generation': goal.generation,
        }

        # 简单计算复杂度分数
        complexity_score = (
            factors['title_length'] / 100.0 +
            (1.0 if factors['has_source'] else 0.0) +
            (0.5 if factors['has_parent'] else 0.0) +
            (0.3 * factors['generation'])
        )

        # 分类复杂度
        if complexity_score < 0.5:
            level = "简单"
        elif complexity_score < 1.5:
            level = "中等"
        else:
            level = "复杂"

        return {
            'level': level,
            'score': complexity_score,
            'factors': factors
        }

    def should_decompose(self, goal: Goal, threshold: float = 1.0) -> bool:
        """判断是否需要分解目标

        Args:
            goal: 目标
            threshold: 分解阈值

        Returns:
            是否需要分解
        """
        complexity = self.estimate_complexity(goal)
        return complexity['score'] >= threshold

    def prioritize_subtasks(
        self,
        subtasks: List[Goal],
        parent_goal: Goal
    ) -> List[Goal]:
        """为子任务设置优先级

        Args:
            subtasks: 子任务列表
            parent_goal: 父目标

        Returns:
            排序后的子任务列表
        """
        # 简单的优先级策略：基于顺序
        # 更复杂的实现可以考虑依赖关系、资源限制等
        for i, subtask in enumerate(subtasks):
            # 这里可以添加更复杂的优先级计算逻辑
            # 例如：基于关键路径、紧急程度等
            pass

        # 返回按创建顺序排序的子任务
        return sorted(subtasks, key=lambda g: g.created_at)
