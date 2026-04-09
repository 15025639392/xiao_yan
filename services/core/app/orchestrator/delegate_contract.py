from __future__ import annotations

from app.domain.models import OrchestratorDelegateRequest, OrchestratorTask

DEFAULT_FORBIDDEN_PATHS = [
    ".git",
    ".data",
    "node_modules",
    "dist",
    "build",
    "target",
]


def build_delegate_request(
    *,
    goal: str,
    project_path: str,
    task: OrchestratorTask,
) -> OrchestratorDelegateRequest:
    return OrchestratorDelegateRequest(
        objective=f"{task.title}。主控总目标：{goal}",
        project_path=project_path,
        scope_paths=task.scope_paths,
        forbidden_paths=DEFAULT_FORBIDDEN_PATHS,
        acceptance_commands=task.acceptance_commands,
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": [
                "status",
                "summary",
                "changed_files",
                "command_results",
                "followup_needed",
                "error",
            ],
            "properties": {
                "status": {"type": "string", "enum": ["succeeded", "failed"]},
                "summary": {"type": "string"},
                "changed_files": {"type": "array", "items": {"type": "string"}},
                "command_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "command",
                            "success",
                            "exit_code",
                            "stdout",
                            "stderr",
                            "duration_ms",
                        ],
                        "properties": {
                            "command": {"type": "string"},
                            "success": {"type": "boolean"},
                            "exit_code": {"type": ["integer", "null"]},
                            "stdout": {"type": ["string", "null"]},
                            "stderr": {"type": ["string", "null"]},
                            "duration_ms": {"type": ["integer", "null"]},
                        },
                    },
                },
                "followup_needed": {"type": "array", "items": {"type": "string"}},
                "error": {"type": ["string", "null"]},
            },
        },
    )


def build_delegate_prompt(request: OrchestratorDelegateRequest) -> str:
    scope_lines = "\n".join(f"- {item}" for item in request.scope_paths) or "- ."
    forbidden_lines = "\n".join(f"- {item}" for item in request.forbidden_paths)
    acceptance_lines = "\n".join(f"- {item}" for item in request.acceptance_commands) or "- 无"
    return (
        "你是小晏主控模式派发出的 Codex delegate。\n"
        "你必须严格服从主控给定边界，只完成当前任务，不要擅自扩散范围。\n\n"
        f"任务目标:\n{request.objective}\n\n"
        f"项目路径:\n{request.project_path}\n\n"
        f"允许改动范围:\n{scope_lines}\n\n"
        f"禁止路径:\n{forbidden_lines}\n\n"
        f"验收命令:\n{acceptance_lines}\n\n"
        "执行要求:\n"
        "1. 先阅读相关代码，再实施最小必要改动。\n"
        "2. 只改 scope_paths 内的文件；如果必须越界，直接失败并说明原因。\n"
        "3. changed_files 必须返回相对项目根路径。\n"
        "4. 如果你执行了命令，请把结果填入 command_results，但最多保留 8 条关键命令。\n"
        "5. command_results 的 stdout/stderr 只保留关键片段，每条建议不超过 400 字，超出写 TRUNCATED。\n"
        "6. summary 只写关键结论，避免粘贴大段日志或文件原文。\n"
        "7. 最终输出必须严格符合提供的 JSON Schema，不要使用 Markdown 代码块。\n"
    )
