from datetime import datetime, timezone
from pathlib import Path

from app.agent.loop import AutonomyLoop
from app.domain.models import BeingState, SelfImprovementEdit, SelfImprovementStatus, WakeMode
from app.goals.repository import InMemoryGoalRepository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
from app.self_improvement.executor import SelfImprovementExecutor
from app.self_improvement.models import SelfImprovementCandidate, SelfImprovementTrigger
from app.self_improvement.planner import SelfImprovementPlanner
from app.self_improvement.service import SelfImprovementService


def _approve_pending_job(store: StateStore) -> None:
    """模拟用户审批：将 pending_approval 的 job 推进到 verifying（供测试用）。"""
    state = store.get()
    job = state.self_improvement_job
    if job and job.status == SelfImprovementStatus.PENDING_APPROVAL:
        approved = job.model_copy(update={"status": SelfImprovementStatus.VERIFYING})
        store.set(state.model_copy(update={"self_improvement_job": approved}))


class StubEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：VALUE 不正确。",
            target_area="agent",
            spec="把 VALUE 从 1 调整到 2。",
            test_commands=["pytest -q test_calculator.py"],
            created_at=now,
        )


class FailureDrivenEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：test_calculator.py::test_value 断言没有通过。",
            target_area="agent",
            spec="根据现有失败测试修复实现。",
            test_commands=["pytest -q test_calculator.py"],
            created_at=now,
        )


class FunctionFailureDrivenEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：test_greeter.py::test_greet 断言没有通过。",
            target_area="agent",
            spec="根据现有失败测试修复 greet 的返回值。",
            test_commands=["pytest -q test_greeter.py"],
            created_at=now,
        )


class CallChainFailureDrivenEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="沿着简单调用链修复真正的返回值实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=now,
        )


class AssignmentCallChainFailureDrivenEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="沿着简单赋值链修复真正的返回值实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=now,
        )


class MultiStepAssignmentFailureDrivenEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="沿着多步局部变量链修复真正的返回值实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=now,
        )


class MultiImportCandidateFailureDrivenEvaluator:
    def evaluate(self, state, recent_events, now):
        return SelfImprovementCandidate(
            trigger=SelfImprovementTrigger.HARD_FAILURE,
            reason="测试失败：test_facade.py::test_wrapper 断言没有通过。",
            target_area="agent",
            spec="在多候选调用里只修真正返回路径上的实现。",
            test_commands=["pytest -q test_facade.py"],
            created_at=now,
        )


class StubPlanner(SelfImprovementPlanner):
    def plan(self, candidate):
        job = super().plan(candidate)
        return job.model_copy(
            update={
                "test_edits": [
                    SelfImprovementEdit(
                        file_path="test_calculator.py",
                        search_text="assert VALUE == 1",
                        replace_text="assert VALUE == 2",
                    )
                ],
                "edits": [
                    SelfImprovementEdit(
                        file_path="calculator.py",
                        search_text="VALUE = 1",
                        replace_text="VALUE = 2",
                    )
                ]
            }
        )


def test_self_improvement_service_can_complete_patch_and_verification_cycle(tmp_path: Path):
    workspace = tmp_path
    (workspace / "calculator.py").write_text("VALUE = 1\n", encoding="utf-8")
    (workspace / "test_calculator.py").write_text(
        "from calculator import VALUE\n\n\ndef test_value():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="self_check", content="测试失败：VALUE 不正确。"))
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=StubEvaluator(),
        planner=StubPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()

    assert first.focus_mode == "self_improvement"
    assert first.self_improvement_job is not None
    assert first.self_improvement_job.status == "diagnosing"
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL 等待用户审批
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    # 模拟用户批准 → 推进到 VERIFYING
    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.focus_mode == "autonomy"
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert fourth.self_improvement_job.verification is not None
    assert fourth.self_improvement_job.verification.passed is True
    assert (workspace / "calculator.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_self_improvement_service_can_use_failure_driven_planner_for_existing_test(tmp_path: Path):
    workspace = tmp_path
    (workspace / "calculator.py").write_text("VALUE = 1\n", encoding="utf-8")
    (workspace / "test_calculator.py").write_text(
        "from calculator import VALUE\n\n\ndef test_value():\n    assert VALUE == 2\n",
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(kind="self_check", content="测试失败：test_calculator.py::test_value 断言没有通过。")
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=FailureDrivenEvaluator(),
        planner=SelfImprovementPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()

    assert first.self_improvement_job is not None
    assert first.self_improvement_job.edits[0].file_path == "calculator.py"
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    # 模拟用户批准
    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert (workspace / "calculator.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_self_improvement_service_can_fix_zero_arg_function_from_existing_test(tmp_path: Path):
    workspace = tmp_path
    (workspace / "greeter.py").write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    (workspace / "test_greeter.py").write_text(
        'from greeter import greet\n\n\ndef test_greet():\n    assert greet() == "hello"\n',
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(kind="self_check", content="测试失败：test_greeter.py::test_greet 断言没有通过。")
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=FunctionFailureDrivenEvaluator(),
        planner=SelfImprovementPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()

    assert first.self_improvement_job is not None
    assert first.self_improvement_job.edits[0].file_path == "greeter.py"
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert (workspace / "greeter.py").read_text(encoding="utf-8") == 'def greet():\n    return "hello"\n'
    workspace = tmp_path
    (workspace / "facade.py").write_text(
        "from greeter import greet\n\n\ndef wrapper():\n    return greet()\n",
        encoding="utf-8",
    )
    (workspace / "greeter.py").write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    (workspace / "test_facade.py").write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(kind="self_check", content="测试失败：test_facade.py::test_wrapper 断言没有通过。")
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=CallChainFailureDrivenEvaluator(),
        planner=SelfImprovementPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()

    assert first.self_improvement_job is not None
    assert first.self_improvement_job.edits[0].file_path == "greeter.py"
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert (workspace / "greeter.py").read_text(encoding="utf-8") == 'def greet():\n    return "hello"\n'


def test_self_improvement_service_can_follow_assignment_then_return_chain_from_existing_test(tmp_path: Path):
    workspace = tmp_path
    (workspace / "facade.py").write_text(
        "from greeter import greet\n\n\ndef wrapper():\n    message = greet()\n    return message\n",
        encoding="utf-8",
    )
    (workspace / "greeter.py").write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    (workspace / "test_facade.py").write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(kind="self_check", content="测试失败：test_facade.py::test_wrapper 断言没有通过。")
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=AssignmentCallChainFailureDrivenEvaluator(),
        planner=SelfImprovementPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()
    fourth = loop.tick_once()

    assert first.self_improvement_job is not None
    assert first.self_improvement_job.edits[0].file_path == "greeter.py"
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert (workspace / "greeter.py").read_text(encoding="utf-8") == 'def greet():\n    return "hello"\n'


def test_self_improvement_service_can_follow_multi_step_assignment_chain_from_existing_test(tmp_path: Path):
    workspace = tmp_path
    (workspace / "facade.py").write_text(
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
    (workspace / "greeter.py").write_text(
        'def greet():\n    return "hi"\n',
        encoding="utf-8",
    )
    (workspace / "test_facade.py").write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(kind="self_check", content="测试失败：test_facade.py::test_wrapper 断言没有通过。")
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=MultiStepAssignmentFailureDrivenEvaluator(),
        planner=SelfImprovementPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()

    assert first.self_improvement_job is not None
    assert first.self_improvement_job.edits[0].file_path == "greeter.py"
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert (workspace / "greeter.py").read_text(encoding="utf-8") == 'def greet():\n    return "hello"\n'


def test_self_improvement_service_chooses_returned_call_from_multi_import_candidates(tmp_path: Path):
    workspace = tmp_path
    (workspace / "facade.py").write_text(
        (
            "from greeter import greet, wave\n\n\n"
            "def wrapper():\n"
            "    first = greet()\n"
            "    second = wave()\n"
            "    return second\n"
        ),
        encoding="utf-8",
    )
    (workspace / "greeter.py").write_text(
        'def greet():\n    return "hi"\n\n\ndef wave():\n    return "bye"\n',
        encoding="utf-8",
    )
    (workspace / "test_facade.py").write_text(
        'from facade import wrapper\n\n\ndef test_wrapper():\n    assert wrapper() == "hello"\n',
        encoding="utf-8",
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(
        MemoryEvent(kind="self_check", content="测试失败：test_facade.py::test_wrapper 断言没有通过。")
    )
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    service = SelfImprovementService(
        evaluator=MultiImportCandidateFailureDrivenEvaluator(),
        planner=SelfImprovementPlanner(workspace_root=workspace),
        executor=SelfImprovementExecutor(workspace),
    )
    loop = AutonomyLoop(
        store,
        repo,
        InMemoryGoalRepository(),
        now_provider=lambda: datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        self_improvement_service=service,
    )

    first = loop.tick_once()
    second = loop.tick_once()
    third = loop.tick_once()

    assert first.self_improvement_job is not None
    assert first.self_improvement_job.edits[0].file_path == "greeter.py"
    assert first.self_improvement_job.edits[0].search_text == 'return "bye"'
    assert second.self_improvement_job.status == "patching"
    # Phase 6: PATCHING 后进入 PENDING_APPROVAL
    assert third.self_improvement_job.status == "pending_approval"
    assert third.self_improvement_job.approval_requested_at is not None

    _approve_pending_job(store)

    fourth = loop.tick_once()
    assert fourth.self_improvement_job is not None
    assert fourth.self_improvement_job.status == "applied"
    assert (workspace / "greeter.py").read_text(encoding="utf-8") == (
        'def greet():\n    return "hi"\n\n\ndef wave():\n    return "hello"\n'
    )
