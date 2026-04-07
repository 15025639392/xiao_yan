from datetime import datetime, timezone
from pathlib import Path

from app.self_programming.models import SelfProgrammingCandidate, SelfProgrammingTrigger
from app.self_programming.planner import SelfProgrammingPlanner
from app.runtime_ext.runtime_config import get_runtime_config


def test_planner_inferrs_python_constant_edit_from_existing_failing_test(tmp_path: Path):
    module_path = tmp_path / "calculator.py"
    test_path = tmp_path / "test_calculator.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")
    test_path.write_text(
        "from calculator import VALUE\n\n\ndef test_value():\n    assert VALUE == 2\n",
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：test_calculator.py::test_value 断言没有通过。",
            target_area="agent",
            spec="根据现有失败测试修复实现。",
            test_commands=["pytest -q test_calculator.py"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "calculator.py"
    assert job.edits[0].search_text == "VALUE = 1"
    assert job.edits[0].replace_text == "VALUE = 2"


def test_planner_inferrs_zero_arg_function_return_edit_from_existing_failing_test(tmp_path: Path):
    module_path = tmp_path / "greeter.py"
    test_path = tmp_path / "test_greeter.py"
    module_path.write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    test_path.write_text(
        'from greeter import greet\n\n\ndef test_greet():\n    assert greet() == "hello"\n',
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：test_greeter.py::test_greet 断言没有通过。",
            target_area="agent",
            spec="根据现有失败测试修复 greet 的返回值。",
            test_commands=["pytest -q test_greeter.py"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "greeter.py"
    assert job.edits[0].search_text == 'return "hi"'
    assert job.edits[0].replace_text == 'return "hello"'


def test_planner_follows_single_hop_zero_arg_call_chain_to_real_implementation(tmp_path: Path):
    facade_path = tmp_path / "facade.py"
    greeter_path = tmp_path / "greeter.py"
    test_path = tmp_path / "test_facade.py"
    facade_path.write_text(
        "from greeter import greet\n\n\ndef wrapper():\n    return greet()\n",
        encoding="utf-8",
    )
    greeter_path.write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    test_path.write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="沿着简单调用链修复真正的返回值实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "greeter.py"
    assert job.edits[0].search_text == 'return "hi"'
    assert job.edits[0].replace_text == 'return "hello"'


def test_planner_follows_single_hop_assignment_then_return_chain_to_real_implementation(tmp_path: Path):
    facade_path = tmp_path / "facade.py"
    greeter_path = tmp_path / "greeter.py"
    test_path = tmp_path / "test_facade.py"
    facade_path.write_text(
        "from greeter import greet\n\n\ndef wrapper():\n    message = greet()\n    return message\n",
        encoding="utf-8",
    )
    greeter_path.write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    test_path.write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="沿着简单赋值链修复真正的返回值实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "greeter.py"
    assert job.edits[0].search_text == 'return "hi"'
    assert job.edits[0].replace_text == 'return "hello"'


def test_planner_follows_multi_step_assignment_chain_to_real_implementation(tmp_path: Path):
    facade_path = tmp_path / "facade.py"
    greeter_path = tmp_path / "greeter.py"
    test_path = tmp_path / "test_facade.py"
    facade_path.write_text(
        (
            "from greeter import greet\n\n\n"
            "def wrapper():\n"
            "    base = greet()\n"
            "    message = base\n"
            "    final = message\n"
            "    return final\n"
        ),
        encoding="utf-8",
    )
    greeter_path.write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    test_path.write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="沿着多步局部变量链修复真正的返回值实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "greeter.py"
    assert job.edits[0].search_text == 'return "hi"'
    assert job.edits[0].replace_text == 'return "hello"'


def test_planner_chooses_returned_call_from_multi_import_candidates(tmp_path: Path):
    facade_path = tmp_path / "facade.py"
    greeter_path = tmp_path / "greeter.py"
    test_path = tmp_path / "test_facade.py"
    facade_path.write_text(
        (
            "from greeter import greet, wave\n\n\n"
            "def wrapper():\n"
            "    first = greet()\n"
            "    second = wave()\n"
            "    return second\n"
        ),
        encoding="utf-8",
    )
    greeter_path.write_text(
        'def greet():\n    return "hi"\n\n\ndef wave():\n    return "bye"\n',
        encoding="utf-8",
    )
    test_path.write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="在多候选调用里只修真正返回路径上的实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "greeter.py"
    assert job.edits[0].search_text == 'return "bye"'
    assert job.edits[0].replace_text == 'return "hello"'


def test_planner_generates_agent_threshold_edit_for_idle_progress_candidate(tmp_path: Path):
    evaluator_path = tmp_path / "services/core/app/self_programming/evaluator.py"
    evaluator_path.parent.mkdir(parents=True, exist_ok=True)
    evaluator_path.write_text(
        "class SelfProgrammingEvaluator:\n    PROACTIVE_EVENT_THRESHOLD = 3\n",
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.PROACTIVE,
            reason="连续多次只产生 thought，没有形成有效行动结果。",
            target_area="agent",
            spec="减少自主循环空转，提升从 thought 到 action 的推进力度。",
            test_commands=["pytest tests/test_autonomy_loop.py -q"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert len(job.edits) == 1
    assert job.edits[0].file_path == "services/core/app/self_programming/evaluator.py"
    assert job.edits[0].search_text == "PROACTIVE_EVENT_THRESHOLD = 3"
    assert job.edits[0].replace_text == "PROACTIVE_EVENT_THRESHOLD = 2"


def test_planner_generates_planning_edit_for_action_command_failure(tmp_path: Path):
    planning_path = tmp_path / "services/core/app/planning/morning_plan.py"
    test_path = tmp_path / "services/core/tests/test_morning_plan_planner.py"
    planning_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    planning_path.write_text(
        (
            "class MorningPlanPlanner:\n"
            "    def action_command_for_goal(self, goal_title: str) -> str | None:\n"
            '        if "目录" in goal_title:\n'
            '            return "date +%H:%M"\n'
            "        return None\n"
        ),
        encoding="utf-8",
    )
    test_path.write_text(
        (
            "from services.core.app.planning.morning_plan import MorningPlanPlanner\n\n\n"
            "def test_planner_action_command():\n"
            '    assert MorningPlanPlanner().action_command_for_goal("看看现在在哪个目录") == "pwd"\n'
        ),
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：晨间计划没有为目录目标生成正确动作。",
            target_area="planning",
            spec="修复晨间计划对目录目标的动作命令。",
            test_commands=["pytest services/core/tests/test_morning_plan_planner.py -q"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert job.test_edits == []
    assert len(job.edits) == 1
    assert job.edits[0].file_path == "services/core/app/planning/morning_plan.py"
    assert job.edits[0].search_text == 'return "date +%H:%M"'
    assert job.edits[0].replace_text == 'return "pwd"'


def test_planner_generates_status_panel_edits_for_missing_self_programming_ui(tmp_path: Path):
    panel_path = tmp_path / "apps/desktop/src/components/StatusPanel.tsx"
    test_path = tmp_path / "apps/desktop/src/components/StatusPanel.test.tsx"
    panel_path.parent.mkdir(parents=True, exist_ok=True)
    panel_path.write_text(
        """import type { BeingState } from "../lib/api";

export function StatusPanel({ state }: { state: BeingState }) {
  return (
    <section>
      <p>阶段: {renderFocusMode(state.focus_mode)}</p>
      {state.today_plan ? <section><h2>她今天的计划</h2></section> : null}
      {state.error ? <p>{state.error}</p> : null}
    </section>
  );
}

function renderFocusMode(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") {
    return "她今天的计划";
  }
  if (focusMode === "autonomy") {
    return "常规自主";
  }
  return "休眠";
}
""",
        encoding="utf-8",
    )
    test_path.write_text(
        """test("renders plan", () => {
  expect(screen.getByText("她今天的计划")).toBeInTheDocument();
});
""",
        encoding="utf-8",
    )
    planner = SelfProgrammingPlanner(workspace_root=tmp_path)

    job = planner.plan(
        SelfProgrammingCandidate(
            trigger=SelfProgrammingTrigger.HARD_FAILURE,
            reason="测试失败：状态面板没有展示自我编程状态。",
            target_area="ui",
            spec="补上自我编程状态展示。",
            test_commands=["npm test -- --run src/components/StatusPanel.test.tsx"],
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )

    assert len(job.test_edits) == 1
    assert job.test_edits[0].file_path == "apps/desktop/src/components/StatusPanel.test.tsx"
    assert "阶段: 自我编程" in job.test_edits[0].replace_text
    assert len(job.edits) == 2
    assert {edit.file_path for edit in job.edits} == {"apps/desktop/src/components/StatusPanel.tsx"}
    assert any("她刚刚为什么改自己" in edit.replace_text for edit in job.edits)
    assert any('if (focusMode === "self_programming")' in edit.replace_text for edit in job.edits)


def test_planner_uses_runtime_cooldown_config_and_snapshots_policy(tmp_path: Path):
    config = get_runtime_config()
    original_hard = config.self_programming_hard_failure_cooldown_minutes
    original_proactive = config.self_programming_proactive_cooldown_minutes
    try:
        config.self_programming_hard_failure_cooldown_minutes = 30
        config.self_programming_proactive_cooldown_minutes = 240

        planner = SelfProgrammingPlanner(workspace_root=tmp_path)
        now = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
        job = planner.plan(
            SelfProgrammingCandidate(
                trigger=SelfProgrammingTrigger.HARD_FAILURE,
                reason="测试失败：X",
                target_area="agent",
                spec="修复",
                test_commands=["pytest -q"],
                created_at=now,
            )
        )

        assert job.cooldown_until == datetime(2026, 4, 5, 10, 30, tzinfo=timezone.utc)
        assert job.cooldown_policy_snapshot == {
            "hard_failure_minutes": 30,
            "proactive_minutes": 240,
        }
    finally:
        config.self_programming_hard_failure_cooldown_minutes = original_hard
        config.self_programming_proactive_cooldown_minutes = original_proactive
