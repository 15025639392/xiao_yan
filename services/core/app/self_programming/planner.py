from pathlib import Path
from datetime import timedelta

from app.domain.models import (
    SelfProgrammingEdit,
    SelfProgrammingJob,
    SelfProgrammingStatus,
    SelfProgrammingVerification,
)
from app.self_programming.models import SelfProgrammingCandidate, SelfProgrammingTrigger
from app.self_programming.planner_inference import PlannerInferenceMixin
from app.runtime_ext.runtime_config import get_runtime_config


class SelfProgrammingPlanner(PlannerInferenceMixin):
    def __init__(self, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root

    def plan(self, candidate: SelfProgrammingCandidate) -> SelfProgrammingJob:
        runtime_config = get_runtime_config()
        hard_minutes = runtime_config.self_programming_hard_failure_cooldown_minutes
        proactive_minutes = runtime_config.self_programming_proactive_cooldown_minutes
        cooldown_minutes = (
            hard_minutes
            if candidate.trigger == SelfProgrammingTrigger.HARD_FAILURE
            else proactive_minutes
        )
        cooldown = timedelta(minutes=cooldown_minutes)
        return SelfProgrammingJob(
            reason=candidate.reason,
            reason_statement=candidate.reason,
            direction_statement=candidate.spec,
            target_area=candidate.target_area,
            status=SelfProgrammingStatus.DRAFTED,
            queue_status=SelfProgrammingStatus.DRAFTED.value,
            owner_type="delegate",
            delegate_provider="codex",
            promotion_status="not_ready",
            spec=candidate.spec,
            test_edits=self._build_test_edits(candidate),
            edits=self._build_edits(candidate),
            verification=SelfProgrammingVerification(commands=candidate.test_commands),
            cooldown_policy_snapshot={
                "hard_failure_minutes": hard_minutes,
                "proactive_minutes": proactive_minutes,
            },
            cooldown_until=(candidate.created_at + cooldown) if candidate.created_at else None,
        )

    def _build_test_edits(self, candidate: SelfProgrammingCandidate) -> list[SelfProgrammingEdit]:
        if self.workspace_root is None:
            return []
        if candidate.target_area == "ui":
            return self._build_ui_test_edits(candidate)
        return []

    def _build_edits(self, candidate: SelfProgrammingCandidate) -> list[SelfProgrammingEdit]:
        if self.workspace_root is None:
            return []

        if candidate.target_area == "agent":
            return self._build_agent_edits(candidate)
        if candidate.target_area == "planning":
            return self._build_planning_edits(candidate)
        if candidate.target_area == "ui":
            return self._build_ui_edits(candidate)
        return []

    def _build_agent_edits(self, candidate: SelfProgrammingCandidate) -> list[SelfProgrammingEdit]:
        if "连续多次只产生 thought" in candidate.reason:
            path = self.workspace_root / "services/core/app/self_programming/evaluator.py"
            if not path.exists():
                return []

            content = path.read_text(encoding="utf-8")
            search_text = "PROACTIVE_EVENT_THRESHOLD = 3"
            if search_text not in content:
                return []

            return [
                SelfProgrammingEdit(
                    file_path="services/core/app/self_programming/evaluator.py",
                    search_text=search_text,
                    replace_text="PROACTIVE_EVENT_THRESHOLD = 2",
                )
            ]

        return self._infer_python_constant_edit(candidate)

    def _build_ui_edits(self, candidate: SelfProgrammingCandidate) -> list[SelfProgrammingEdit]:
        if "状态面板没有展示自我编程状态" not in candidate.reason:
            return []

        path = self.workspace_root / "apps/desktop/src/components/StatusPanel.tsx"
        if not path.exists():
            return []

        content = path.read_text(encoding="utf-8")
        edits: list[SelfProgrammingEdit] = []

        phase_search = (
            '  if (focusMode === "autonomy") {\n'
            '    return "常规自主";\n'
            "  }\n"
            '  return "休眠";'
        )
        if 'if (focusMode === "self_programming")' not in content and phase_search in content:
            edits.append(
                SelfProgrammingEdit(
                    file_path="apps/desktop/src/components/StatusPanel.tsx",
                    search_text=phase_search,
                    replace_text=(
                        '  if (focusMode === "autonomy") {\n'
                        '    return "常规自主";\n'
                        "  }\n"
                        '  if (focusMode === "self_programming") {\n'
                        '    return "自我编程";\n'
                        "  }\n"
                        '  return "休眠";'
                    ),
                )
            )

        panel_search = "      {state.error ? <p>{state.error}</p> : null}\n"
        if "她刚刚为什么改自己" not in content and panel_search in content:
            edits.append(
                SelfProgrammingEdit(
                    file_path="apps/desktop/src/components/StatusPanel.tsx",
                    search_text=panel_search,
                    replace_text=(
                        "      {state.self_programming_job ? (\n"
                        "        <section>\n"
                        "          <h2>她刚刚为什么改自己</h2>\n"
                        "          <p>Area: {state.self_programming_job.target_area}</p>\n"
                        "          <p>Reason: {state.self_programming_job.reason}</p>\n"
                        "        </section>\n"
                        "      ) : null}\n"
                        "      {state.error ? <p>{state.error}</p> : null}\n"
                    ),
                )
            )

        return edits

    def _build_planning_edits(self, candidate: SelfProgrammingCandidate) -> list[SelfProgrammingEdit]:
        method_call_edit = self._infer_class_method_return_edit(candidate)
        if method_call_edit:
            return method_call_edit
        return self._infer_python_constant_edit(candidate)

    def _build_ui_test_edits(self, candidate: SelfProgrammingCandidate) -> list[SelfProgrammingEdit]:
        if "状态面板没有展示自我编程状态" not in candidate.reason:
            return []

        path = self.workspace_root / "apps/desktop/src/components/StatusPanel.test.tsx"
        if not path.exists():
            return []

        content = path.read_text(encoding="utf-8")
        search_text = '  expect(screen.getByText("她今天的计划")).toBeInTheDocument();\n'
        if "阶段: 自我编程" in content or search_text not in content:
            return []

        return [
            SelfProgrammingEdit(
                file_path="apps/desktop/src/components/StatusPanel.test.tsx",
                search_text=search_text,
                replace_text=(
                    '  expect(screen.getByText("她今天的计划")).toBeInTheDocument();\n'
                    '  expect(screen.getByText("阶段: 自我编程")).toBeInTheDocument();\n'
                ),
            )
        ]
