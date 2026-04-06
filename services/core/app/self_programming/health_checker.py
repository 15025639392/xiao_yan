"""
自我编程健康度评估器（Facade）。

拆分说明：
- 数据模型与维度定义：app.self_programming.health_models
- 评分/趋势纯函数：app.self_programming.health_scoring
- 本模块保留 HealthChecker 编排逻辑与历史兼容导出
"""

from __future__ import annotations

from typing import Any

from app.self_programming.health_models import (
    HEALTH_DIMENSIONS,
    HealthDimensionScore,
    HealthGrade,
    HealthReport,
    HealthSignal,
    HealthTrend,
)
from app.self_programming.health_scoring import (
    compute_current_trend,
    compute_history_trend,
    detect_degrading_files,
    generate_recommendations,
    index_signals,
    score_conflict_rate,
    score_dimension,
    score_file_stability,
    score_programming_frequency,
    score_rollback_rate,
    score_test_pass_rate,
    score_to_grade,
)


class HealthChecker:
    """自我编程健康度评估器。"""

    DEFAULT_ROLLBACK_THRESHOLD = 40.0
    DEFAULT_DEGRADING_THRESHOLD = 3
    MAX_HISTORY_REPORTS = 50

    def __init__(
        self,
        rollback_threshold: float | None = None,
        degrading_threshold: int | None = None,
    ) -> None:
        self.rollback_threshold = rollback_threshold or self.DEFAULT_ROLLBACK_THRESHOLD
        self.degrading_threshold = degrading_threshold or self.DEFAULT_DEGRADING_THRESHOLD
        self._report_history: list[HealthReport] = []

    def check(
        self,
        signals: list[HealthSignal] | None = None,
        history: list[Any] | None = None,
        recent_rollbacks: int = 0,
        recent_conflicts: int = 0,
    ) -> HealthReport:
        dimensions = self._score_all_dimensions(
            signals=signals,
            history=history,
            recent_rollbacks=recent_rollbacks,
            recent_conflicts=recent_conflicts,
        )

        overall = sum(d.weighted_score for d in dimensions)
        grade = self._score_to_grade(overall)
        degrading_files = self._detect_degrading_files(history) if history else []
        recommendations = self._generate_recommendations(overall, dimensions, degrading_files)
        rollback_advised, rollback_reason = self.should_rollback(
            overall, grade, degrading_files, recent_rollbacks
        )
        trend = self._compute_trend(overall)

        report = HealthReport(
            overall_score=round(overall, 1),
            grade=grade,
            trend=trend,
            dimensions=dimensions,
            signals_used=signals or [],
            recommendations=recommendations,
            degrading_files=degrading_files,
            rollback_advised=rollback_advised,
            rollback_reason=rollback_reason,
        )

        self._report_history.append(report)
        if len(self._report_history) > self.MAX_HISTORY_REPORTS:
            self._report_history = self._report_history[-self.MAX_HISTORY_REPORTS :]

        return report

    def should_rollback(
        self,
        overall_score: float | None = None,
        grade: HealthGrade | None = None,
        degrading_files: list[str] | None = None,
        recent_rollbacks: int = 0,
        report: HealthReport | None = None,
    ) -> tuple[bool, str]:
        if report:
            overall_score = report.overall_score
            grade = report.grade
            degrading_files = report.degrading_files

        reasons: list[str] = []

        if overall_score is not None and overall_score < self.rollback_threshold:
            reasons.append(
                f"健康分 ({overall_score:.0f}) 低于阈值 ({self.rollback_threshold})"
            )
        if grade == HealthGrade.CRITICAL:
            reasons.append("系统健康等级为危险")
        if degrading_files and len(degrading_files) >= 3:
            reasons.append(f"{len(degrading_files)} 个文件出现退化迹象")
        if recent_rollbacks >= 2:
            reasons.append(f"近期已有 {recent_rollbacks} 次回滚，问题可能更深层")

        if reasons:
            return True, "; ".join(reasons)
        return False, ""

    def get_trend(self) -> HealthTrend:
        return compute_history_trend(self._report_history)

    def get_degrading_files(self, history: list[Any]) -> list[str]:
        return self._detect_degrading_files(history)

    def _score_all_dimensions(
        self,
        signals: list[HealthSignal] | None,
        history: list[Any] | None,
        recent_rollbacks: int,
        recent_conflicts: int,
    ) -> list[HealthDimensionScore]:
        signal_map = self._index_signals(signals)
        results: list[HealthDimensionScore] = []

        for dim_name, weight, _label in HEALTH_DIMENSIONS:
            ds = score_dimension(
                dim_name=dim_name,
                weight=weight,
                signal_map=signal_map,
                history=history,
                recent_rollbacks=recent_rollbacks,
                recent_conflicts=recent_conflicts,
                degrading_threshold=self.degrading_threshold,
            )
            ds.weighted_score = round(ds.score * weight / 100, 2)
            results.append(ds)

        return results

    def _score_test_pass_rate(self, signal_map: dict[str, HealthSignal]) -> HealthDimensionScore:
        return score_test_pass_rate(signal_map)

    def _score_programming_frequency(
        self,
        signal_map: dict[str, HealthSignal],
        history: list[Any] | None,
    ) -> HealthDimensionScore:
        return score_programming_frequency(signal_map, history)

    def _score_rollback_rate(
        self,
        recent_rollbacks: int,
        history: list[Any] | None,
    ) -> HealthDimensionScore:
        return score_rollback_rate(recent_rollbacks, history)

    def _score_conflict_rate(
        self,
        recent_conflicts: int,
        history: list[Any] | None,
    ) -> HealthDimensionScore:
        return score_conflict_rate(recent_conflicts, history)

    def _score_file_stability(self, history: list[Any] | None) -> HealthDimensionScore:
        return score_file_stability(history, self.degrading_threshold)

    @staticmethod
    def _index_signals(signals: list[HealthSignal] | None) -> dict[str, HealthSignal]:
        return index_signals(signals)

    @staticmethod
    def _score_to_grade(score: float) -> HealthGrade:
        return score_to_grade(score)

    def _detect_degrading_files(self, history: list[Any] | None) -> list[str]:
        return detect_degrading_files(history, self.degrading_threshold)

    def _generate_recommendations(
        self,
        overall: float,
        dimensions: list[HealthDimensionScore],
        degrading_files: list[str],
    ) -> list[str]:
        return generate_recommendations(overall, dimensions, degrading_files)

    def _compute_trend(self, current_score: float) -> HealthTrend:
        return compute_current_trend(current_score, self._report_history)


__all__ = [
    "HealthTrend",
    "HealthGrade",
    "HealthSignal",
    "HealthDimensionScore",
    "HealthReport",
    "HEALTH_DIMENSIONS",
    "HealthChecker",
]
