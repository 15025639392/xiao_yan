from __future__ import annotations

from app.domain.models import OrchestratorPlan, OrchestratorTask, OrchestratorTaskKind, ProjectSnapshot


class OrchestratorPlanner:
    def build_plan(self, goal: str, project_snapshot: ProjectSnapshot) -> OrchestratorPlan:
        implementation_scopes = self._implementation_scopes(project_snapshot)
        verification_commands = self._verification_commands(project_snapshot)
        read_scope = self._read_scope(project_snapshot)

        tasks: list[OrchestratorTask] = [
            OrchestratorTask(
                task_id="analyze-1",
                title="分析当前项目结构、启动链路和改动落点",
                kind=OrchestratorTaskKind.ANALYZE,
                scope_paths=read_scope,
                acceptance_commands=["git status --short"],
            ),
        ]

        implement_ids: list[str] = []
        total_implement = len(implementation_scopes)
        for index, scope_paths in enumerate(implementation_scopes, start=1):
            task_id = f"implement-{index}"
            implement_ids.append(task_id)
            scope_hint = "、".join(scope_paths[:2]) if scope_paths else "."
            tasks.append(
                OrchestratorTask(
                    task_id=task_id,
                    title=f"围绕目标实现改动（{index}/{total_implement}）：{goal}（范围：{scope_hint}）",
                    kind=OrchestratorTaskKind.IMPLEMENT,
                    scope_paths=scope_paths,
                    acceptance_commands=self._acceptance_for_scope(scope_paths, verification_commands),
                    depends_on=["analyze-1"],
                )
            )

        verify_task_id = "verify-1"
        tasks.extend(
            [
            OrchestratorTask(
                task_id=verify_task_id,
                title="执行计划内验收命令并汇总结果",
                kind=OrchestratorTaskKind.VERIFY,
                scope_paths=["."],
                acceptance_commands=verification_commands or ["git status --short"],
                depends_on=implement_ids,
            ),
            OrchestratorTask(
                task_id="summarize-1",
                title="整理最终摘要、风险和后续建议（本地执行）",
                kind=OrchestratorTaskKind.SUMMARIZE,
                scope_paths=["."],
                acceptance_commands=["git status --short"],
                depends_on=[verify_task_id],
            ),
        ]
        )

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

    def _implementation_scopes(self, project_snapshot: ProjectSnapshot) -> list[list[str]]:
        scopes: list[list[str]] = []
        used_signatures: set[tuple[str, ...]] = set()

        if project_snapshot.framework == "tauri":
            frontend_scope = self._dedupe(
                [
                    *[item for item in project_snapshot.entry_files if not item.startswith("src-tauri/")],
                    *[item for item in project_snapshot.key_directories if item in {"src", "apps"}],
                    "package.json",
                ]
            )
            rust_scope = self._dedupe(
                [
                    *[item for item in project_snapshot.entry_files if item.startswith("src-tauri/")],
                    "src-tauri",
                    "Cargo.toml",
                ]
            )
            for scope in [frontend_scope, rust_scope]:
                signature = tuple(scope)
                if not scope or signature in used_signatures:
                    continue
                used_signatures.add(signature)
                scopes.append(scope)

        if not scopes:
            for directory in project_snapshot.key_directories:
                scope = self._dedupe([directory])
                signature = tuple(scope)
                if not scope or signature in used_signatures:
                    continue
                used_signatures.add(signature)
                scopes.append(scope)

        if not scopes:
            fallback_scope = self._dedupe(project_snapshot.entry_files + project_snapshot.key_directories)
            scopes.append(fallback_scope or ["."])

        return scopes

    def _verification_commands(self, project_snapshot: ProjectSnapshot) -> list[str]:
        return self._dedupe(project_snapshot.test_commands + project_snapshot.build_commands)

    def _acceptance_for_scope(self, scope_paths: list[str], verification_commands: list[str]) -> list[str]:
        if not verification_commands:
            return ["git diff --name-only"]

        is_tauri_scope = any(path.startswith("src-tauri") or path == "Cargo.toml" for path in scope_paths)
        if is_tauri_scope:
            cargo_command = next((command for command in verification_commands if "cargo " in command), None)
            if cargo_command:
                return [cargo_command]

        non_cargo = next((command for command in verification_commands if "cargo " not in command), None)
        if non_cargo:
            return [non_cargo]
        return [verification_commands[0]]

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
