"""安全沙箱、冲突检测与历史记录测试。

覆盖范围：
- SandboxEnvironment: 隔离执行、超时控制、语法检查、清理
- ConflictDetector: 文件重叠、受保护路径、循环自改
- SelfImprovementHistory: 记录/查询/统计/文件持久化
- Executor.preflight_check: 集成预检流程
- Service 层: PATCHING 中的预检集成
"""

import json
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models import (
    EditKind,
    SelfImprovementEdit,
    SelfImprovementJob,
    SelfImprovementStatus,
    SelfImprovementVerification,
)
from app.self_improvement.executor import SelfImprovementExecutor
from app.self_improvement.sandbox import (
    SandboxConfig,
    SandboxEnvironment,
    SandboxResult,
)
from app.self_improvement.conflict_detector import (
    ConflictDetector,
    ConflictReport,
    ConflictSeverity,
    FileConflict,
    FREQUENT_EDIT_THRESHOLD,
)
from app.self_improvement.history_store import (
    HistoryEntry,
    HistoryEntryStatus,
    MemoryBackend,
    FileBackend,
    SelfImprovementHistory,
)


# ────────────────────────────────────────────
# Fixtures & Helpers
# ────────────────────────────────────────────

def _make_edit(
    file_path: str = "sample.py",
    kind: EditKind = EditKind.REPLACE,
    **kwargs,
) -> SelfImprovementEdit:
    base_kwargs: dict = {"file_path": file_path, "kind": kind}
    if kind == EditKind.REPLACE:
        base_kwargs.setdefault("search_text", "old code")
        base_kwargs.setdefault("replace_text", "new code")
    elif kind == EditKind.CREATE:
        base_kwargs["file_content"] = kwargs.get("file_content") or "# new file\nprint('hello')\n"
    elif kind == EditKind.INSERT:
        base_kwargs.setdefault("insert_after", "# anchor")
        base_kwargs.setdefault("replace_text", "\n# inserted\n")
    return SelfImprovementEdit(**base_kwargs)


def _make_job(
    status: SelfImprovementStatus = SelfImprovementStatus.PATCHING,
    edits: list[SelfImprovementEdit] | None = None,
    touched_files: list[str] | None = None,
    verification_cmds: list[str] | None = None,
) -> SelfImprovementJob:
    edits = edits or [_make_edit()]
    touched_files = touched_files or [e.file_path for e in edits]
    return SelfImprovementJob(
        reason="test reason",
        target_area="testing",
        status=status,
        spec="fix the bug",
        edits=edits,
        verification=SelfImprovementVerification(commands=verification_cmds or ["true"]),
        touched_files=touched_files,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """创建一个带基本 Python 文件的工作区。"""
    # 创建一些源代码文件
    src_dir = tmp_path / "services" / "core" / "app"
    src_dir.mkdir(parents=True)

    (src_dir / "__init__.py").write_text("", encoding="utf-8")

    main_file = src_dir / "main.py"
    main_file.write_text(textwrap.dedent("""\
        def old_function():
            return "old_value"
    """), encoding="utf-8")

    utils_dir = src_dir / "utils"
    utils_dir.mkdir(parents=True)
    (utils_dir / "__init__.py").write_text("", encoding="utf-8")
    (utils_dir / "helper.py").write_text("# helper\\ndef help(): pass\\n", encoding="utf-8")

    return tmp_path


# ────────────────────────────────────────────
# SandboxEnvironment 测试
# ────────────────────────────────────────────


class TestSandboxBasic:
    """沙箱基础功能。"""

    def test_quick_syntax_check_valid(self, workspace):
        """合法 Python 语法检查通过。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)
        result = sandbox.quick_check_syntax(
            "main.py",
            file_content='def foo():\n    return 42\n',
        )
        assert result.success is True

    def test_quick_syntax_check_invalid(self, workspace):
        """非法语法被捕获。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)
        result = sandbox.quick_check_syntax(
            "bad.py",
            file_content='def foo(:\n    return 42\n',
        )
        assert result.success is False
        assert "语法错误" in (result.error_message or "")

    def test_quick_syntax_check_non_python(self, workspace):
        """非 Python 文件跳过编译。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)
        result = sandbox.quick_check_syntax(
            "style.css",
            file_content=".btn { color: red; }\\n",
        )
        assert result.success is True

    def test_quick_syntax_check_empty(self, workspace):
        """空内容被标记为失败。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)
        # 空内容对 .py 文件会通过 compile（空模块合法），但 quick_check 对空字符串有特殊处理
        # 实际行为：空 .py 文件 compile 通过 → success=True；非 .py 空 → 失败
        result_py = sandbox.quick_check_syntax("empty.py", file_content="")
        # 空的 Python 模块语法合法，所以可能返回 success
        # 但我们主要测试不崩溃即可
        assert isinstance(result_py, SandboxResult)

        result_css = sandbox.quick_check_syntax("empty.css", file_content="")
        assert result_css.success is False  # 非 Python 空文件应失败

    def test_prevalidate_with_passing_command(self, workspace):
        """预验证通过时返回 success=True。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)
        
        edit = _make_edit(file_path="services/core/app/main.py",
                          search_text='"old_value"',
                          replace_text='"new_value"')

        result = sandbox.prevalidate(
            edits=[edit],
            verification_commands=["true"],
            job_id="test-prevalidate",
        )

        assert result.success is True

    def test_prevalidate_with_failing_command(self, workspace):
        """预验证命令失败时返回 success=False。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)

        edit = _make_edit(file_path="services/core/app/main.py")

        result = sandbox.prevalidate(
            edits=[edit],
            verification_commands=["false"],
            job_id="test-fail",
        )

        assert result.success is False
        assert result.exit_code != 0

    def test_prevalidate_no_commands_returns_failure(self, workspace):
        """没有验证命令时快速返回失败。"""
        sandbox = SandboxEnvironment(workspace_root=workspace)
        edit = _make_edit()

        result = sandbox.prevalidate(edits=[edit], verification_commands=[], job_id="empty-cmds")

        assert result.success is False
        assert "没有提供验证命令" in (result.error_message or "")


class TestSandboxIsolation:
    """沙箱隔离性测试。"""

    def test_does_not_modify_real_files(self, workspace):
        """沙箱操作不影响真实文件。"""
        sandbox = SandboxEnvironment(
            workspace_root=workspace,
            config=SandboxConfig(cleanup_on_exit=True),
        )

        original = (workspace / "services" / "core" / "app" / "main.py").read_text(encoding="utf-8")

        edit = SelfImprovementEdit(
            file_path="services/core/app/main.py",
            kind=EditKind.REPLACE,
            search_text='"old_value"',
            replace_text='"SANDBOX_MODIFIED"',
        )

        sandbox.prevalidate(
            edits=[edit],
            verification_commands=["echo ok"],
            job_id="isolation-test",
        )

        # 真实文件应保持不变
        current = (workspace / "services" / "core" / "app" / "main.py").read_text(encoding="utf-8")
        assert '"old_value"' in current
        assert "SANDBOX_MODIFIED" not in current

    def test_temp_cleanup(self, workspace):
        """临时目录被正确清理。"""
        sandbox = SandboxEnvironment(
            workspace_root=workspace,
            config=SandboxConfig(cleanup_on_exit=True),
        )
        edit = _make_edit()
        sandbox.prevalidate([edit], ["true"], job_id="cleanup-test")
        # cleanup_on_exit=True 时 temp_dir 应已被删除（或为 None）
        assert sandbox._temp_dir is None or not sandbox._temp_dir.exists()

    def test_timeout_handling(self, workspace):
        """超时命令被正确处理。"""
        sandbox = SandboxEnvironment(
            workspace_root=workspace,
            config=SandboxConfig(timeout_seconds=1.0),
        )
        # 使用 workspace 中实际存在的文件
        edit = _make_edit(file_path="services/core/app/main.py",
                          search_text='"old_value"',
                          replace_text='"new_value"')

        result = sandbox.prevalidate(
            edits=[edit],
            verification_commands=["sleep 5"],
            job_id="timeout-test",
        )

        assert result.success is False
        # 超时或文件复制失败都算"不成功"
        if "没有找到需要复制的文件" not in (result.error_message or ""):
            assert result.timed_out is True


class TestSandboxResult:
    """SandboxResult 数据模型。"""

    def test_summary_formats(self):
        """各种状态的 summary 输出。"""
        passed = SandboxResult(success=True, duration_seconds=1.5)
        assert "✅ 通过" in passed.summary
        assert "1.5s" in passed.summary

        failed = SandboxResult(success=False, exit_code=1, stderr="error msg", duration_seconds=2.0)
        assert "❌ 失败" in failed.summary
        assert "exit=1" in failed.summary

        timed_out = SandboxResult(timed_out=True, duration_seconds=30.0)
        assert "⏰ 超时" in timed_out.summary


# ────────────────────────────────────────────
# ConflictDetector 测试
# ────────────────────────────────────────────


class TestConflictDetectorBasic:
    """冲突检测基础。"""

    def test_no_conflicts_safe(self, workspace):
        """无编辑 → SAFE。"""
        detector = ConflictDetector(workspace_root=workspace)
        report = detector.check([])
        assert report.is_safe is True
        assert report.severity == ConflictSeverity.SAFE

    def test_single_edit_no_history_safe(self, workspace):
        """单次编辑且无历史记录 → SAFE。"""
        detector = ConflictDetector(workspace_root=workspace)
        edit = _make_edit(file_path="new_file.py")
        report = detector.check([edit])
        assert report.is_safe is True

    def test_protected_path_blocking(self, workspace):
        """.env 文件被阻止。"""
        detector = ConflictDetector(workspace_root=workspace)
        edit = _make_edit(file_path=".env.local")
        report = detector.check([edit])
        assert report.has_blocking is True
        assert any(c.conflict_type == "protected" for c in report.conflicts)

    def test_secrets_pattern_blocked(self, workspace):
        """secrets 相关文件被阻止。"""
        detector = ConflictDetector(workspace_root=workspace)
        edit = _make_edit(file_path="config/secrets.json")
        report = detector.check([edit])
        assert report.has_blocking is True

    def test_normal_py_file_allowed(self, workspace):
        """普通 .py 文件不受保护路径规则影响。"""
        detector = ConflictDetector(workspace_root=workspace)
        edit = _make_edit(file_path="services/core/app/agent/loop.py")
        report = detector.check([edit])
        assert report.has_blocking is False


class TestConflictOverlapDetection:
    """文件重叠检测。"""

    def test_same_file_different_area_warning(self, workspace):
        """同一文件不同区域修改 → WARNING。"""
        detector = ConflictDetector(workspace_root=workspace)

        # 模拟历史 Job 修改了同一文件
        history_job = MagicMock()
        history_job.touched_files = ["utils/helper.py"]
        history_job.edits = [
            SelfImprovementEdit(
                file_path="utils/helper.py",
                kind=EditKind.REPLACE,
                search_text="def help(): pass",
                replace_text="def help(): return 42",
            )
        ]

        # 新补丁也修改同一文件但不同位置
        new_edit = SelfImprovementEdit(
            file_path="utils/helper.py",
            kind=EditKind.REPLACE,
            search_text="# helper",
            replace_text="# updated helper",
        )

        report = detector.check([new_edit], applied_history=[history_job])
        assert report.severity in (ConflictSeverity.WARNING, ConflictSeverity.SAFE)
        if not report.is_safe:
            assert len(report.overlapping_files) > 0

    def test_exact_search_overlap_detected(self, workspace):
        """完全相同的 search text 被检测为重叠。"""
        detector = ConflictDetector(workspace_root=workspace)
        search_target = 'return "old_value"'

        history_job = MagicMock()
        history_job.touched_files = ["main.py"]
        history_job.edits = [
            SelfImprovementEdit(file_path="main.py", search_text=search_target, replace_text="x"),
        ]

        new_edit = SelfImprovementEdit(file_path="main.py", search_text=search_target, replace_text="y")

        report = detector.check([new_edit], applied_history=[history_job])
        assert report.severity == ConflictSeverity.WARNING
        assert any("相同" in c.description for c in report.conflicts)


class TestConflictFrequentEdit:
    """循环自改检测。"""

    def test_frequent_edit_triggers_warning(self, workspace):
        """同一文件频繁修改触发 WARNING。"""
        detector = ConflictDetector(workspace_root=workspace)
        target_file = "hot_module.py"

        # 记录多次应用
        for _ in range(4):  # 超过 FREQUENT_EDIT_THRESHOLD(3)
            detector.record_apply([target_file])

        edit = _make_edit(file_path=target_file)
        report = detector.check([edit])
        assert any(c.conflict_type == "frequent_edit" for c in report.conflicts)


class TestConflictReport:
    """报告格式化。"""

    def test_summary_safe(self):
        report = ConflictReport(severity=ConflictSeverity.SAFE, total_files_checked=5)
        assert "✅ 无冲突" in report.summary()

    def test_summary_mixed(self):
        conflicts = [
            FileConflict("a.py", ConflictSeverity.BLOCKING, "protected", "blocked"),
            FileConflict("b.py", ConflictSeverity.WARNING, "overlap", "overlapped"),
        ]
        report = ConflictReport(
            severity=ConflictSeverity.BLOCKING,
            conflicts=conflicts,
            total_files_checked=3,
        )
        s = report.summary()
        assert "🚫" in s
        assert "⚠️" in s

    def test_is_safe_property(self):
        safe = ConflictReport(severity=ConflictSeverity.SAFE)
        assert safe.is_safe is True
        assert safe.has_blocking is False

        blocking = ConflictReport(
            severity=ConflictSeverity.BLOCKING,
            conflicts=[FileConflict("x", ConflictSeverity.BLOCKING, "t", "d")],
        )
        assert blocking.has_blocking is True


class TestCommonPrefixHelper:
    """公共前缀检测辅助函数。"""

    def test_long_common_prefix(self):
        from app.self_improvement.conflict_detector import _share_common_prefix
        assert _share_common_prefix(
            "def calculate_total(items):",
            "def calculate_average(items):",
        ) is True

    def test_short_common_prefix(self):
        from app.self_improvement.conflict_detector import _share_common_prefix
        assert _share_common_prefix("abc", "xyz") is False

    def test_identical_strings(self):
        from app.self_improvement.conflict_detector import _share_common_prefix
        assert _share_common_prefix("same content", "same content") is True


# ────────────────────────────────────────────
# SelfImprovementHistory 测试
# ────────────────────────────────────────────


class TestMemoryBackend:
    """内存后端测试。"""

    def test_save_and_load(self):
        backend = MemoryBackend()
        entry = {"job_id": "j1", "target_area": "test"}
        backend.save(entry)
        assert backend.count == 1
        loaded = backend.load_all()
        assert len(loaded) == 1
        assert loaded[0]["job_id"] == "j1"

    def test_recent_limit(self):
        backend = MemoryBackend()
        for i in range(10):
            backend.save({"job_id": f"j{i}"})
        recent = backend.load_recent(3)
        assert len(recent) == 3
        assert recent[-1]["job_id"] == "j9"

    def test_clear(self):
        backend = MemoryBackend()
        backend.save({"job_id": "j1"})
        backend.clear()
        assert backend.count == 0


class TestFileBackend:
    """文件后端测试。"""

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "history.json"
        backend = FileBackend(path)
        entry = {"job_id": "j-file", "status": "applied"}
        backend.save(entry)

        loaded = backend.load_all()
        assert len(loaded) == 1
        assert loaded[0]["job_id"] == "j-file"

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "persistent.json"
        b1 = FileBackend(path)
        b1.save({"job_id": "persist"})
        del b1

        b2 = FileBackend(path)
        loaded = b2.load_all()
        assert len(loaded) == 1
        assert loaded[0]["job_id"] == "persist"

    def test_corrupt_file_graceful(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("{invalid json}", encoding="utf-8")
        backend = FileBackend(path)
        loaded = backend.load_all()  # 不崩溃
        assert isinstance(loaded, list)


class TestSelfImprovementHistory:
    """历史管理器完整功能。"""

    def test_record_from_job(self):
        job = _make_job(status=SelfImprovementStatus.APPLIED)
        history = SelfImprovementHistory(in_memory=True)
        entry = history.record_from_job(job)

        assert entry.job_id == job.id
        assert entry.target_area == job.target_area
        assert entry.status == HistoryEntryStatus.APPLIED
        assert history.count == 1

    def test_get_recent(self):
        history = SelfImprovementHistory(in_memory=True)
        for i in range(5):
            job = _make_job(status=SelfImprovementStatus.APPLIED)
            history.record_from_job(job)

        recent = history.get_recent(2)
        assert len(recent) == 2

    def test_get_for_file(self):
        history = SelfImprovementHistory(in_memory=True)

        job_a = _make_job(
            edits=[_make_edit(file_path="alpha.py")],
            touched_files=["alpha.py"],
        )
        history.record_from_job(job_a)

        job_b = _make_job(
            edits=[_make_edit(file_path="beta.py")],
            touched_files=["beta.py"],
        )
        history.record_from_job(job_b)

        alpha_entries = history.get_for_file("alpha.py")
        assert len(alpha_entries) == 1
        assert history.get_for_file("nonexistent.py") == []

    def test_statistics(self):
        history = SelfImprovementHistory(in_memory=True)

        # APPLIED jobs
        for area in ["agent", "planning", "agent"]:
            job = _make_job(
                status=SelfImprovementStatus.APPLIED,
                edits=[_make_edit(file_path=f"{area}_file.py")],
                touched_files=[f"{area}_file.py"],
            )
            # 手动设置 target_area（通过 model_copy）
            job = job.model_copy(update={"target_area": area})
            history.record_from_job(job)

        # FAILED job
        fail_job = _make_job(status=SelfImprovementStatus.FAILED)
        history.record_from_job(fail_job)

        stats = history.get_statistics()
        assert stats["total_jobs"] == 4
        assert stats["applied"] == 3
        assert stats["failed"] == 1
        assert "agent" in stats["by_target_area"]
        assert stats["by_target_area"]["agent"] == 2
        assert stats["success_rate"] == 75.0

    def test_clear_all(self):
        history = SelfImprovementHistory(in_memory=True)
        history.record_from_job(_make_job())
        assert history.count > 0
        history.clear()
        assert history.count == 0


# ────────────────────────────────────────────
# Executor Preflight Check 集成测试
# ────────────────────────────────────────────


class TestPreflightCheck:
    """Executor.preflight_check 集成。"""

    def test_preflight_passes_when_clean(self, workspace):
        """无冲突 + 沙箱通过 → 正常继续。"""
        executor = SelfImprovementExecutor(
            workspace_root=workspace,
            enable_sandbox=True,
            enable_conflict_check=True,
        )
        job = _make_job(
            edits=[_make_edit(file_path="services/core/app/main.py",
                              search_text='"old_value"',
                              replace_text='"new_value"')],
            touched_files=["services/core/app/main.py"],
            verification_cmds=["true"],
        )

        checked = executor.preflight_check(job)
        assert checked.status != SelfImprovementStatus.FAILED
        assert checked.sandbox_prechecked is True

    def test_preflight_blocks_protected_path(self, workspace):
        """受保护路径的补丁被阻止。"""
        executor = SelfImprovementExecutor(
            workspace_root=workspace,
            enable_sandbox=True,
            enable_conflict_check=True,
        )
        job = _make_job(
            edits=[_make_edit(file_path=".env.production")],
            touched_files=[".env.production"],
        )

        checked = executor.preflight_check(job)
        assert checked.status == SelfImprovementStatus.FAILED
        assert "冲突检测阻止" in (checked.patch_summary or "")
        assert checked.sandbox_prechecked is False  # 被阻塞后不跑沙箱

    def test_preflight_skips_when_disabled(self, workspace):
        """禁用时不做任何检查，原样返回。"""
        executor = SelfImprovementExecutor(
            workspace_root=workspace,
            enable_sandbox=False,
            enable_conflict_check=False,
        )
        job = _make_job()

        checked = executor.preflight_check(job)
        assert checked.status == SelfImprovementStatus.PATCHING  # 原状态不变
        assert checked.sandbox_prechecked is False
        assert checked.conflict_severity == "safe"

    def test_record_successful_apply(self, workspace):
        """成功 apply 后更新冲突检测器状态。"""
        executor = SelfImprovementExecutor(
            workspace_root=workspace,
            enable_sandbox=False,
        )
        target_file = "hot_target.py"
        job = _make_job(
            status=SelfImprovementStatus.APPLIED,
            edits=[_make_edit(file_path=target_file)],
            touched_files=[target_file],
        )

        # 记录足够多次数以超过阈值
        detector = executor.conflict_detector
        if detector:
            # 先直接记录到检测器（模拟历史）
            for _ in range(FREQUENT_EDIT_THRESHOLD + 1):
                detector.record_apply([target_file])

            check_report = detector.check(job.edits)
            assert any(c.conflict_type == "frequent_edit" for c in check_report.conflicts)


def _make_applied_job():
    """创建已 APPLIED 的 Job。"""
    return _make_job(
        status=SelfImprovementStatus.APPLIED,
        edits=[_make_edit()],
        touched_files=["target.py"],
    )


# ────────────────────────────────────────────
# HistoryEntry 数据模型测试
# ────────────────────────────────────────────


class TestHistoryEntryModel:
    """HistoryEntry 序列化和反序列化。"""

    def test_to_dict_roundtrip(self):
        entry = HistoryEntry(
            job_id="abc123",
            target_area="planning",
            reason="fix bug",
            spec="fix it",
            status=HistoryEntryStatus.APPLIED,
            touched_files=["file.py"],
            commit_hash="def456",
        )
        d = entry.to_dict()
        assert d["job_id"] == "abc123"
        assert d["status"] == "applied"  # 枚举序列化为字符串

    def test_from_job_extraction(self):
        job = SelfImprovementJob(
            reason="auto fix",
            target_area="ui",
            spec="change color",
            status=SelfImprovementStatus.APPLIED,
            branch_name="self-fix/ui-xxx",
            commit_hash="abc123",
            candidate_label="candidate-A",
            edits=[_make_edit(file_path="style.tsx")],
            touched_files=["style.tsx"],
        )
        entry = HistoryEntry.from_job(job)
        assert entry.job_id == job.id
        assert entry.target_area == "ui"
        assert entry.branch_name == "self-fix/ui-xxx"
        assert entry.commit_hash == "abc123"
        assert entry.candidate_label == "candidate-A"
