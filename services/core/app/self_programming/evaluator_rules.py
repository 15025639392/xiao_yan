from __future__ import annotations


def infer_target_area(reason: str) -> str:
    if "前端" in reason or "状态面板" in reason or "UI" in reason:
        return "ui"
    if "计划" in reason:
        return "planning"
    return "agent"


def build_hard_failure_spec(reason: str) -> str:
    return f"修复当前硬故障：{reason}"


def default_test_commands(target_area: str) -> list[str]:
    if target_area == "ui":
        return [
            "npm test -- --run src/App.test.tsx src/components/StatusPanel.test.tsx",
        ]
    if target_area == "planning":
        return ["pytest tests/test_morning_plan_planner.py -q"]
    return ["pytest tests/test_autonomy_loop.py -q"]


__all__ = [
    "infer_target_area",
    "build_hard_failure_spec",
    "default_test_commands",
]
