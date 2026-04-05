from pathlib import Path

from app.domain.models import (
    SelfImprovementEdit,
    SelfImprovementJob,
    SelfImprovementStatus,
    SelfImprovementVerification,
)
from app.self_improvement.executor import SelfImprovementExecutor


def test_executor_applies_edit_and_keeps_changes_after_passing_verification(tmp_path: Path):
    workspace = tmp_path
    (workspace / "calculator.py").write_text("VALUE = 1\n", encoding="utf-8")
    (workspace / "test_calculator.py").write_text(
        "from calculator import VALUE\n\n\ndef test_value():\n    assert VALUE == 2\n",
        encoding="utf-8",
    )
    executor = SelfImprovementExecutor(workspace)
    job = SelfImprovementJob(
        reason="测试失败：VALUE 不正确",
        target_area="agent",
        status=SelfImprovementStatus.PATCHING,
        spec="把 VALUE 调整为 2",
        edits=[
            SelfImprovementEdit(
                file_path="calculator.py",
                search_text="VALUE = 1",
                replace_text="VALUE = 2",
            )
        ],
        verification=SelfImprovementVerification(commands=["pytest -q test_calculator.py"]),
    )

    patched = executor.apply(job)
    verified = executor.verify(patched)

    assert patched.status == SelfImprovementStatus.VERIFYING
    assert verified.status == SelfImprovementStatus.APPLIED
    assert verified.verification is not None
    assert verified.verification.passed is True
    assert (workspace / "calculator.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_executor_reverts_changes_after_failed_verification(tmp_path: Path):
    workspace = tmp_path
    (workspace / "calculator.py").write_text("VALUE = 1\n", encoding="utf-8")
    (workspace / "test_calculator.py").write_text(
        "from calculator import VALUE\n\n\ndef test_value():\n    assert VALUE == 3\n",
        encoding="utf-8",
    )
    executor = SelfImprovementExecutor(workspace)
    job = SelfImprovementJob(
        reason="测试失败：VALUE 不正确",
        target_area="agent",
        status=SelfImprovementStatus.PATCHING,
        spec="把 VALUE 调整为 2",
        edits=[
            SelfImprovementEdit(
                file_path="calculator.py",
                search_text="VALUE = 1",
                replace_text="VALUE = 2",
            )
        ],
        verification=SelfImprovementVerification(commands=["pytest -q test_calculator.py"]),
    )

    patched = executor.apply(job)
    verified = executor.verify(patched)

    assert verified.status == SelfImprovementStatus.FAILED
    assert verified.verification is not None
    assert verified.verification.passed is False
    assert (workspace / "calculator.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_executor_runs_red_green_cycle_with_test_edits_before_implementation(tmp_path: Path):
    workspace = tmp_path
    (workspace / "calculator.py").write_text("VALUE = 1\n", encoding="utf-8")
    (workspace / "test_calculator.py").write_text(
        "from calculator import VALUE\n\n\ndef test_value():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    executor = SelfImprovementExecutor(workspace)
    job = SelfImprovementJob(
        reason="测试失败：需要先把回归测试写出来。",
        target_area="agent",
        status=SelfImprovementStatus.PATCHING,
        spec="先让测试要求 VALUE == 2，再修改实现。",
        test_edits=[
            SelfImprovementEdit(
                file_path="test_calculator.py",
                search_text="assert VALUE == 1",
                replace_text="assert VALUE == 2",
            )
        ],
        edits=[
            SelfImprovementEdit(
                file_path="calculator.py",
                search_text="VALUE = 1",
                replace_text="VALUE = 2",
            )
        ],
        verification=SelfImprovementVerification(commands=["pytest -q test_calculator.py"]),
    )

    patched = executor.apply(job)
    verified = executor.verify(patched)

    assert patched.status == SelfImprovementStatus.VERIFYING
    assert patched.red_verification is not None
    assert patched.red_verification.passed is False
    assert "assert VALUE == 2" in (workspace / "test_calculator.py").read_text(encoding="utf-8")
    assert verified.status == SelfImprovementStatus.APPLIED
    assert verified.verification is not None
    assert verified.verification.passed is True
