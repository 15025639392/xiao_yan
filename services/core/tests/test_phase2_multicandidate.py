"""Phase 2: 候选评分器 + 多候选 A/B 测试的测试。"""

import textwrap
from datetime import datetime
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
from app.self_improvement.scorer import CandidateScorer, ScoredCandidate, RISK_PENALTIES


# ────────────────────────────────────────────
# CandidateScorer 测试
# ────────────────────────────────────────────


class TestCandidateScorerBasicScoring:
    """基础评分逻辑测试。"""

    def test_high_confidence_scores_high(self):
        scorer = CandidateScorer()
        job = _make_job(edits=[_make_edit("test_file.py")])
        scored = scorer.score(job, {"confidence": 0.95, "risk_level": "low"})
        assert scored.score_confidence == 0.95
        assert scored.total_score > 0.8

    def test_low_risk_gets_full_score(self):
        scorer = CandidateScorer()
        job = _make_job(edits=[_make_edit("test_file.py")])
        scored = scorer.score(job, {"confidence": 0.8, "risk_level": "low"})
        assert scored.score_risk == RISK_PENALTIES["low"]  # 1.0

    def test_high_risk_gets_penalty(self):
        scorer = CandidateScorer()
        job = _make_job(edits=[_make_edit("core/main.py")])
        scored = scorer.score(job, {"confidence": 0.8, "risk_level": "high"})
        assert scored.score_risk == RISK_PENALTIES["high"]  # 0.2

    def test_single_edit_is_simpler_than_multiple(self):
        scorer = CandidateScorer()
        simple = _make_job(edits=[_make_edit("file.py")])
        complex_ = _make_job(edits=[
            _make_edit("file.py"),
            _make_edit("other.py"),
            _make_edit("third.py"),
        ])
        score_simple = scorer.score(simple).score_simplicity
        score_complex = scorer.score(complex_).score_simplicity
        assert score_simple > score_complex

    def test_test_files_get_safety_bonus(self):
        scorer = CandidateScorer()
        test_job = _make_job(edits=[_make_edit("tests/test_foo.py")])
        core_job = _make_job(edits=[_make_edit("main.py")])
        safety_test = scorer.score(test_job).score_safety
        safety_core = scorer.score(core_job).score_safety
        assert safety_test > safety_core

    def test_total_score_in_range(self):
        scorer = CandidateScorer()
        for conf in [0.0, 0.3, 0.5, 0.8, 1.0]:
            for risk in ["low", "medium", "high"]:
                job = _make_job(edits=[_make_edit("file.py")])
                scored = scorer.score(job, {"confidence": conf, "risk_level": risk})
                assert 0.0 <= scored.total_score <= 1.0

    def test_explain_produces_readable_output(self):
        scorer = CandidateScorer()
        job = _make_job(edits=[_make_edit("file.py")])
        scored = scorer.score(job, {"id": "A", "confidence": 0.8, "risk_level": "low"})
        explanation = scorer.explain(scored)
        assert "候选 A" in explanation  # explain 使用中文输出
        assert "置信度" in explanation
        assert "风险" in explanation


class TestCandidateScorerRanking:
    """排序测试：确保评分器能正确区分优劣方案。"""

    def test_low_risk_beats_high_risk_same_confidence(self):
        scorer = CandidateScorer()
        edits = [_make_edit("some_file.py")]
        low_risk = scorer.score(_make_job(edits=edits), {
            "confidence": 0.7, "risk_level": "low"
        })
        high_risk = scorer.score(_make_job(edits=edits), {
            "confidence": 0.7, "risk_level": "high"
        })
        assert low_risk.total_score > high_risk.total_score

    def test_high_confidence_beats_low_same_risk(self):
        scorer = CandidateScorer()
        edits = [_make_edit("some_file.py")]
        high_conf = scorer.score(_make_job(edits=edits), {
            "confidence": 0.9, "risk_level": "medium"
        })
        low_conf = scorer.score(_make_job(edits=edits), {
            "confidence": 0.3, "risk_level": "medium"
        })
        assert high_conf.total_score > low_conf.total_score

    def test_simple_edits_beats_complex_same_other_factors(self):
        scorer = CandidateScorer()
        meta = {"confidence": 0.7, "risk_level": "medium", "id": "X"}
        simple = scorer.score(_make_job(edits=[_make_edit("a.py")]), meta)
        complex_ = scorer.score(_make_job(edits=[
            _make_edit("a.py"), _make_edit("b.py"), _make_edit("c.py"),
        ]), meta)
        assert simple.total_score > complex_.total_score

    def test_no_edits_gives_perfect_simplicity_and_safety(self):
        scorer = CandidateScorer()
        empty = scorer.score(_make_job(edits=[]), {})
        assert empty.score_simplicity == 1.0
        assert empty.score_safety == 1.0


# ────────────────────────────────────────────
# Executor.try_best 测试
# ────────────────────────────────────────────


class TestExecutorTryBest:
    """多候选 A/B 测试执行器测试。"""

    def test_selects_first_passing_candidate(self, sample_workspace):
        executor = self._make_executor(sample_workspace)
        candidates = [
            # candidate-A: 应该失败（search_text 不匹配）
            self._scored_with_edits(sample_workspace, "A", [
                SelfImprovementEdit(
                    file_path="target.txt",
                    search_text="NOT_EXISTING_TEXT",
                    replace_text="new content",
                )
            ]),
            # candidate-B: 应该成功（search_text 匹配，验证命令也通过）
            self._scored_with_edits(sample_workspace, "B", [
                SelfImprovementEdit(
                    file_path="target.txt",
                    search_text="original",
                    replace_text="patched",
                )
            ], verification_cmds=["true"]),  # 用 true 让验证通过
        ]
        result = executor.try_best(candidates)
        assert result is not None
        assert result.status == SelfImprovementStatus.APPLIED
        assert "selected=B" in (result.patch_summary or "")

    def test_returns_none_when_all_fail(self, tmp_path):
        executor = self._make_executor(tmp_path)
        bad_edit = SelfImprovementEdit(
            file_path="target.txt",
            search_text="NOT_EXISTING",
            replace_text="anything",
        )
        candidates = [self._scored_with_edits(tmp_path, f"C-{i}", [bad_edit]) for i in range(3)]
        result = executor.try_best(candidates)
        assert result is None

    def test_respects_max_attempts(self, tmp_path):
        executor = self._make_executor(tmp_path)
        bad_edit = SelfImprovementEdit(
            file_path="target.txt",
            search_text="NOT_EXISTING",
            replace_text="anything",
        )
        # 3 个候选但 max_attempts=1，只尝试第一个
        candidates = [self._scored_with_edits(tmp_path, f"D-{i}", [bad_edit]) for i in range(3)]
        result = executor.try_best(candidates, max_attempts=1)
        assert result is None  # 第一个就失败了

    @staticmethod
    def _make_executor(workspace: Path) -> object:
        from app.self_improvement.executor import SelfImprovementExecutor
        return SelfImprovementExecutor(workspace)

    @staticmethod
    def _scored_with_edits(
        workspace: Path,
        cand_id: str,
        edits: list[SelfImprovementEdit],
        verification_cmds: list[str] | None = None,
    ) -> ScoredCandidate:
        from app.self_improvement.scorer import CandidateScorer
        job = SelfImprovementJob(
            reason="test",
            target_area="agent",
            status=SelfImprovementStatus.PATCHING,
            spec="test spec",
            edits=edits,
            verification=SelfImprovementVerification(commands=verification_cmds or ["true"]),
        )
        return CandidateScorer().score(job, {"id": cand_id, "confidence": 0.7})


# ────────────────────────────────────────────
# LLMPlanner 多候选解析测试
# ────────────────────────────────────────────


class TestLLMPlannerMultiCandidateParsing:
    """LLM 输出解析：多候选格式 + 向后兼容单候选格式。"""

    def test_parse_multiple_candidates(self):
        response = textwrap.dedent("""\
        ```json
        {
          "diagnosis": "阈值需要降低",
          "candidates": [
            {
              "id": "conservative",
              "description": "只改常量值",
              "edits": [{"file_path": "evaluator.py", "kind": "replace", "search_text": "THRESHOLD = 3", "replace_text": "THRESHOLD = 2"}],
              "confidence": 0.95,
              "risk_level": "low"
            },
            {
              "id": "moderate",
              "description": "改常量并加日志",
              "edits": [
                {"file_path": "evaluator.py", "kind": "replace", "search_text": "THRESHOLD = 3", "replace_text": "THRESHOLD = 2"},
                {"file_path": "logger.py", "kind": "insert", "insert_after": "import logging", "replace_text": "\\nlog = logging.getLogger()"}
              ],
              "confidence": 0.75,
              "risk_level": "medium"
            }
          ]
        }
        ```
        """)
        from app.self_improvement.llm_planner import LLMPlanner
        parsed = LLMPlanner._parse_multi_candidate_response(response)
        assert len(parsed) == 2
        assert parsed[0][0] == "conservative"
        assert len(parsed[0][1]) == 1  # conservative 有 1 个 edit
        assert parsed[1][0] == "moderate"
        assert len(parsed[1][1]) == 2  # moderate 有 2 个 edits

    def test_parse_single_candidate_backward_compat(self):
        """旧格式（没有 candidates 数组）应该仍然能解析。"""
        response = textwrap.dedent("""\
        ```json
        {
          "diagnosis": "简单修复",
          "edits": [{"file_path": "foo.py", "kind": "replace", "search_text": "old", "replace_text": "new"}],
          "confidence": 0.8,
          "risk_level": "low"
        }
        ```
        """)
        from app.self_improvement.llm_planner import LLMPlanner
        parsed = LLMPlanner._parse_multi_candidate_response(response)
        assert len(parsed) == 1
        assert parsed[0][1][0].file_path == "foo.py"

    def test_parse_create_kind(self):
        response = textwrap.dedent("""\
        {
          "diagnosis": "缺少测试文件",
          "candidates": [{
            "id": "create-test",
            "description": "创建新测试文件",
            "edits": [{"file_path": "tests/test_new_feature.py", "kind": "create", "file_content": "def test_new():\\n    assert True"}],
            "confidence": 0.85,
            "risk_level": "low"
          }]
        }
        """)
        from app.self_improvement.llm_planner import LLMPlanner
        parsed = LLMPlanner._parse_multi_candidate_response(response)
        assert len(parsed) == 1
        edit = parsed[0][1][0]
        assert edit.kind == EditKind.CREATE
        assert edit.file_content is not None
        assert "def test_new()" in edit.file_content

    def test_parse_insert_kind(self):
        response = textwrap.dedent("""\
        {
          "diagnosis": "需要添加导入",
          "candidates": [{
            "id": "add-import",
            "description": "在现有导入后插入新导入",
            "edits": [{"file_path": "module.py", "kind": "insert", "insert_after": "import os", "replace_text": "\\nimport json"}],
            "confidence": 0.9,
            "risk_level": "low"
          }]
        }
        """)
        from app.self_improvement.llm_planner import LLMPlanner
        parsed = LLMPlanner._parse_multi_candidate_response(response)
        assert len(parsed) == 1
        edit = parsed[0][1][0]
        assert edit.kind == EditKind.INSERT
        assert edit.insert_after == "import os"

    def test_empty_candidates_returns_empty_list(self):
        response = '{"diagnosis": "no fix", "candidates": [], "explanation": "cannot fix"}'
        from app.self_improvement.llm_planner import LLMPlanner
        parsed = LLMPlanner._parse_multi_candidate_response(response)
        assert parsed == []

    def test_invalid_json_returns_empty_list(self):
        from app.self_improvement.llm_planner import LLMPlanner
        parsed = LLMPlanner._parse_multi_candidate_response("this is not json at all")
        assert parsed == []


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────


def _make_edit(file_path: str = "file.py", kind=EditKind.REPLACE) -> SelfImprovementEdit:
    if kind == EditKind.REPLACE:
        return SelfImprovementEdit(
            file_path=file_path, search_text="old", replace_text="new", kind=kind,
        )
    if kind == EditKind.CREATE:
        return SelfImprovementEdit(
            file_path=file_path, file_content="# new file\n", kind=kind,
        )
    return SelfImprovementEdit(
        file_path=file_path, insert_after="# end", replace_text="\n# added\n", kind=kind,
    )


def _make_job(
    reason: str = "test reason",
    target_area: str = "agent",
    edits: list | None = None,
) -> SelfImprovementJob:
    return SelfImprovementJob(
        reason=reason,
        target_area=target_area,
        status=SelfImprovementStatus.PATCHING,
        spec="test spec",
        edits=edits or [],
        verification=SelfImprovementVerification(commands=[]),
    )


@pytest.fixture()
def sample_workspace(tmp_path: Path) -> Path:
    """创建一个包含示例文件的临时工作区用于测试。"""
    (tmp_path / "target.txt").write_text("original line here\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text("x = 42\n", encoding="utf-8")
    return tmp_path
