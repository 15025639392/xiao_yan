import json
import re
from typing import Protocol

from app.domain.models import TodayPlan, TodayPlanStep, TodayPlanStepKind
from app.goals.models import Goal
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage


class MorningPlanDraftGenerator(Protocol):
    def generate(self, goal: Goal, recent_autobio: str | None = None) -> list[dict] | None:
        ...


class LLMMorningPlanDraftGenerator:
    def __init__(self, gateway: ChatGateway) -> None:
        self.gateway = gateway

    def generate(self, goal: Goal, recent_autobio: str | None = None) -> list[dict] | None:
        context = "" if recent_autobio is None else f"\n最近自传式回顾：{recent_autobio}"
        result = self.gateway.create_response(
            [
                ChatMessage(
                    role="user",
                    content=(
                        f"请为目标“{goal.title}”生成今天早上的两步计划草案。"
                        "如果第一步适合执行安全命令，可以使用 action step。"
                        f"{context}"
                    ),
                )
            ],
            instructions=(
                "只输出 JSON。格式为 {\"steps\":[{\"content\":\"...\",\"kind\":\"reflect|action\","
                "\"command\":\"可选\"}, ...]}。至少两步。"
            ),
        )
        return _parse_draft_steps(result.output_text)


class MorningPlanPlanner:
    def __init__(self, allowed_commands: set[str] | None = None) -> None:
        self.allowed_commands = allowed_commands or {"pwd", "date"}

    def build_plan(
        self,
        goal: Goal,
        draft_steps: list[dict] | None = None,
        draft_generator: MorningPlanDraftGenerator | None = None,
        recent_autobio: str | None = None,
    ) -> TodayPlan:
        if draft_steps is None and draft_generator is not None:
            draft_steps = draft_generator.generate(goal, recent_autobio=recent_autobio)
        return TodayPlan(
            goal_id=goal.id,
            goal_title=goal.title,
            steps=self.normalize_steps(goal, draft_steps),
        )

    def build_steps(self, goal: Goal) -> list[TodayPlanStep]:
        action_command = self.action_command_for_goal(goal.title)
        if action_command is not None:
            return [
                TodayPlanStep(
                    content=f"先执行一个小动作来推进“{goal.title}”",
                    kind=TodayPlanStepKind.ACTION,
                    command=action_command,
                ),
                TodayPlanStep(content="看一眼结果，再决定下一步"),
            ]
        if goal.chain_id and goal.generation >= 2:
            return [
                TodayPlanStep(content=f"回看“{goal.title}”停在了哪里"),
                TodayPlanStep(content="决定是继续推进还是先收束"),
            ]
        if goal.chain_id:
            return [
                TodayPlanStep(content=f"顺着“{goal.title}”把今天要推进的一小步理清"),
                TodayPlanStep(content="开始行动"),
            ]
        return [
            TodayPlanStep(content=f"把“{goal.title}”的轮廓理一下"),
            TodayPlanStep(content="开始动手推进"),
        ]

    def build_plan_summary(self, goal: Goal) -> str:
        first_step, second_step = self.build_steps(goal)
        return f" 先{first_step.content}，再{second_step.content}。"

    def build_plan_summary_from_plan(self, plan: TodayPlan) -> str:
        first_step, second_step = plan.steps[:2]
        return f" 先{first_step.content}，再{second_step.content}。"

    def action_command_for_goal(self, goal_title: str) -> str | None:
        if "时间" in goal_title or "几点" in goal_title:
            return "date +%H:%M"
        if "目录" in goal_title or "文件" in goal_title:
            return "pwd"
        return None

    def normalize_steps(self, goal: Goal, draft_steps: list[dict] | None = None) -> list[TodayPlanStep]:
        fallback_steps = self.build_steps(goal)
        if not draft_steps or len(draft_steps) < 2:
            return fallback_steps

        normalized: list[TodayPlanStep] = []
        for raw_step in draft_steps:
            step = TodayPlanStep.model_validate(raw_step)
            if not step.content.strip():
                return fallback_steps
            if step.kind == TodayPlanStepKind.ACTION:
                if step.command is None:
                    return fallback_steps
                executable = step.command.strip().split()[0]
                if executable not in self.allowed_commands:
                    return fallback_steps
            normalized.append(step)

        return normalized if len(normalized) >= 2 else fallback_steps


def _parse_draft_steps(output_text: str) -> list[dict] | None:
    for candidate in _draft_json_candidates(output_text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            steps = data.get("steps")
            return steps if isinstance(steps, list) else None

        if isinstance(data, list):
            return data

    return None


def _draft_json_candidates(output_text: str) -> list[str]:
    text = output_text.strip()
    if not text:
        return []

    candidates: list[str] = [text]

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and start < end:
            snippet = text[start : end + 1].strip()
            if snippet and snippet not in candidates:
                candidates.append(snippet)

    return candidates
