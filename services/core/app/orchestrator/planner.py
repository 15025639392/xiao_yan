from __future__ import annotations

from app.domain.models import OrchestratorPlan, OrchestratorTask, OrchestratorTaskKind, ProjectSnapshot


class OrchestratorPlanner:
    def build_plan(self, goal: str, project_snapshot: ProjectSnapshot) -> OrchestratorPlan:
        implementation_scope = self._implementation_scope(project_snapshot)
        verification_commands = self._verification_commands(project_snapshot)
        read_scope = self._read_scope(project_snapshot)

        tasks = [
            OrchestratorTask(
                task_id="analyze-1",
                title="分析当前项目结构、启动链路和改动落点",
                kind=OrchestratorTaskKind.ANALYZE,
                scope_paths=read_scope,
                acceptance_commands=["git status --short"],
            ),
            OrchestratorTask(
                task_id="implement-1",
                title=f"围绕目标实现改动：{goal}",
                kind=OrchestratorTaskKind.IMPLEMENT,
                scope_paths=implementation_scope,
                acceptance_commands=verification_commands[:1] or ["git diff --name-only"],
                depends_on=["analyze-1"],
            ),
            OrchestratorTask(
                task_id="verify-1",
                title="执行计划内验收命令并汇总结果",
                kind=OrchestratorTaskKind.VERIFY,
                scope_paths=["."],
                acceptance_commands=verification_commands or ["git status --short"],
                depends_on=["implement-1"],
            ),
            OrchestratorTask(
                task_id="summarize-1",
                title="整理最终摘要、风险和后续建议",
                kind=OrchestratorTaskKind.SUMMARIZE,
                scope_paths=["."],
                acceptance_commands=["git status --short"],
                depends_on=["verify-1"],
            ),
        ]

        return OrchestratorPlan(
            objective=goal,
            constraints=[
                "只在已审批的 scope_paths 内分析或修改项目。",
                "不得触碰 forbidden_paths、.git、依赖产物目录和主控边界之外的文件。",
                "优先复用项目现有的构建与测试命令，不额外引入新流程。",
                "所有结论都要回收到结构化摘要中，便于主控统一验收。",
            ],
            definition_of_done=[
                "结构化计划已审批并完成 analyze -> implement -> verify -> summarize。",
                "delegate 回填了变更摘要、改动文件和执行结果。",
                "计划内验收命令全部执行并产出统一验证结论。",
            ],
            project_snapshot=project_snapshot,
            tasks=tasks,
        )

    def _read_scope(self, project_snapshot: ProjectSnapshot) -> list[str]:
        return self._dedupe(project_snapshot.entry_files + project_snapshot.key_directories + ["package.json", "Cargo.toml"])

    def _implementation_scope(self, project_snapshot: ProjectSnapshot) -> list[str]:
        scope = list(project_snapshot.entry_files)
        scope.extend(project_snapshot.key_directories)
        if project_snapshot.framework == "tauri":
            scope.extend(["src-tauri", "package.json", "Cargo.toml"])
        return self._dedupe(scope) or ["."]

    def _verification_commands(self, project_snapshot: ProjectSnapshot) -> list[str]:
        return self._dedupe(project_snapshot.test_commands + project_snapshot.build_commands)

    def _dedupe(self, items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = item.strip().strip("/")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped
