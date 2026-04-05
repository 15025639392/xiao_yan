"""
自我编程健康度评估器

在自我编程补丁应用后，评估系统健康状态：

1. 多维健康评分 — 从 5 个维度打分（总分 100）
2. 信号收集 — 收集测试失败率/频率/模式等健康信号
3. 退化检测 — 检测"越改越坏"的退化趋势
4. 回滚决策 — 根据健康分数决定是否需要回滚
5. 趋势分析 — 追踪健康度的历史变化方向

与 ConflictDetector 的关系：
- ConflictDetector 在 apply 前检查（预防）
- HealthChecker 在 apply 后评估（诊断）
- 两者形成 前置防御 + 后置监控 的完整闭环
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────


class HealthTrend(str, Enum):
    """健康度趋势。"""

    IMPROVING = "improving"       # 越来越好
    STABLE = "stable"             # 稳定
    DEGRADING = "degrading"      # 恶化中
    CRITICAL = "critical"        # 危急，需立即干预


class HealthGrade(str, Enum):
    """健康等级。"""

    EXCELLENT = "excellent"     # 90-100: 优秀
    GOOD = "good"               # 75-89: 良好
    FAIR = "fair"               # 60-74: 及格
    POOR = "poor"               # 40-59: 较差
    CRITICAL = "critical"       # 0-39: 危险


@dataclass
class HealthSignal:
    """单个健康信号 — 来自系统运行的原始数据点。"""

    source: str                  # 信号来源（如 "test_runner", "conflict_detector"）
    metric: str                  # 指标名（如 "test_pass_rate", "edit_frequency"）
    value: float                 # 数值
    unit: str = ""               # 单位（如 "%", "count/hour"）
    timestamp: str = ""          # ISO 时间戳
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", datetime.now(timezone.utc).isoformat())


@dataclass
class HealthDimensionScore:
    """单个维度的评分详情。"""

    name: str                    # 维度名
    score: float                 # 0~100
    weight: float                # 权重
    weighted_score: float        # 加权分 = score * weight / 100
    details: str = ""            # 人类可读的详细说明

    @property
    def display(self) -> str:
        return f"{self.name}: {self.score:.0f}/100 (×{self.weight}) = {self.weighted_score:.1f}"


@dataclass
class HealthReport:
    """完整的健康报告。"""

    overall_score: float         # 0~100 总分
    grade: HealthGrade           # 健康等级
    trend: HealthTrend = HealthTrend.STABLE
    dimensions: list[HealthDimensionScore] = field(default_factory=list)
    signals_used: list[HealthSignal] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    degrading_files: list[str] = field(default_factory=list)
    rollback_advised: bool = False
    rollback_reason: str = ""
    generated_at: str = ""
    window_seconds: float = 3600  # 评估时间窗口

    def __post_init__(self) -> None:
        if not self.generated_at:
            object.__setattr__(self, "generated_at", datetime.now(timezone.utc).isoformat())

    @property
    def summary(self) -> str:
        """一行摘要。"""
        grade_emoji = {
            HealthGrade.EXCELLENT: "💚",
            HealthGrade.GOOD: "💙",
            HealthGrade.FAIR: "💛",
            HealthGrade.POOR: "🧡",
            HealthGrade.CRITICAL: "❤️‍🩹",
        }
        emoji = grade_emoji.get(self.grade, "?")
        trend_arrow = {
            HealthTrend.IMPROVING: "📈",
            HealthTrend.STABLE: "➡️",
            HealthTrend.DEGRADING: "📉",
            HealthTrend.CRITICAL: "🚨",
        }
        arrow = trend_arrow.get(self.trend, "")
        roll_tag = " ⚠️ 建议回滚" if self.rollback_advised else ""
        return f"{emoji} 健康 {self.overall_score:.0f}/100 ({self.grade.value}) {arrow}{roll_tag}"

    @property
    def full_report(self) -> str:
        """多行详细报告。"""
        lines = [f"=== 自我编程健康度报告 ===", f""]
        lines.append(f"总分: {self.overall_score:.1f}/100  |  等级: {self.grade.value}  |  趋势: {self.trend.value}")
        lines.append(f"时间: {self.generated_at}  |  窗口: {self.window_seconds / 3600:.1f}h")
        lines.append(f"")

        lines.append("--- 各维度评分 ---")
        for dim in self.dimensions:
            bar_len = int(dim.score / 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            lines.append(f"  {bar} {dim.display}")
            if dim.details:
                lines.append(f"      └ {dim.details}")

        if self.degrading_files:
            lines.append("")
            lines.append(f"--- 退化的文件 ({len(self.degrading_files)}) ---")
            for fp in self.degrading_files[:10]:
                lines.append(f"  📉 {fp}")

        if self.recommendations:
            lines.append("")
            lines.append("--- 建议 ---")
            for rec in self.recommendations:
                lines.append(f"  • {rec}")

        if self.rollback_advised:
            lines.append("")
            lines.append(f"⚠️ 回滚建议: {self.rollback_reason}")

        return "\n".join(lines)


# ── 维度定义 ────────────────────────────────────────────

# (名称, 权重, 描述)
HEALTH_DIMENSIONS = [
    ("test_pass_rate", 35, "测试通过率"),
    ("programming_frequency", 20, "自我编程频率"),
    ("rollback_rate", 20, "近期回滚率"),
    ("conflict_rate", 15, "冲突告警比例"),
    ("file_stability", 10, "文件修改稳定性"),
]


# ── 主类 ────────────────────────────────────────────────


class HealthChecker:
    """自我编程健康度评估器。

    用法::

        checker = HealthChecker()

        # 收集信号
        signals = [
            HealthSignal("test_runner", "test_pass_rate", 95.0, "%"),
            HealthSignal("internal", "programming_count", 3.0, "count"),
        ]

        # 评估健康度
        report = checker.check(signals=signals, history=history_entries)

        if report.rollback_advised:
            recovery.smart_rollback(job_id, ...)
    """

    # 默认阈值
    DEFAULT_ROLLBACK_THRESHOLD = 40.0    # 低于此分数建议回滚
    DEFAULT_DEGRADING_THRESHOLD = 3       # 文件被修改 N 次以上标记为退化

    # 最大历史报告数（用于趋势分析）
    MAX_HISTORY_REPORTS = 50

    def __init__(
        self,
        rollback_threshold: float | None = None,
        degrading_threshold: int | None = None,
    ) -> None:
        """
        Args:
            rollback_threshold: 低于此分数建议回滚（默认 40）
            degrading_threshold: 文件修改次数超过此值标记为退化（默认 3）
        """
        self.rollback_threshold = rollback_threshold or self.DEFAULT_ROLLBACK_THRESHOLD
        self.degrading_threshold = degrading_threshold or self.DEFAULT_DEGRADING_THRESHOLD

        # 历史报告（用于趋势分析）
        self._report_history: list[HealthReport] = []

    # ── 核心 API ──────────────────────────────────

    def check(
        self,
        signals: list[HealthSignal] | None = None,
        history: list[Any] | None = None,
        recent_rollbacks: int = 0,
        recent_conflicts: int = 0,
    ) -> HealthReport:
        """执行一次完整的健康检查。

        Args:
            signals: 原始健康信号列表
            history: 最近的自我编程历史条目（HistoryEntry 或类似对象）
            recent_rollbacks: 近期回滚次数
            recent_conflicts: 近期冲突告警数

        Returns:
            完整的健康报告
        """
        dimensions = self._score_all_dimensions(
            signals=signals,
            history=history,
            recent_rollbacks=recent_rollbacks,
            recent_conflicts=recent_conflicts,
        )

        # 计算总分
        overall = sum(d.weighted_score for d in dimensions)

        # 确定等级
        grade = self._score_to_grade(overall)

        # 检测退化文件
        degrading_files = self._detect_degrading_files(history) if history else []

        # 生成建议
        recommendations = self._generate_recommendations(overall, dimensions, degrading_files)

        # 决定是否建议回滚
        rollback_advised, rollback_reason = self.should_rollback(
            overall, grade, degrading_files, recent_rollbacks
        )

        # 趋势分析
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

        # 存入历史用于后续趋势分析
        self._report_history.append(report)
        if len(self._report_history) > self.MAX_HISTORY_REPORTS:
            self._report_history = self._report_history[-self.MAX_HISTORY_REPORTS:]

        return report

    def should_rollback(
        self,
        overall_score: float | None = None,
        grade: HealthGrade | None = None,
        degrading_files: list[str] | None = None,
        recent_rollbacks: int = 0,
        report: HealthReport | None = None,
    ) -> tuple[bool, str]:
        """判断是否应该触发回滚。

        Returns:
            (是否建议回滚, 原因说明)
        """
        if report:
            overall_score = report.overall_score
            grade = report.grade
            degrading_files = report.degrading_files

        reasons: list[str] = []

        # 条件 1: 总分过低
        if overall_score is not None and overall_score < self.rollback_threshold:
            reasons.append(
                f"健康分 ({overall_score:.0f}) 低于阈值 ({self.rollback_threshold})"
            )

        # 条件 2: 等级为危险
        if grade == HealthGrade.CRITICAL:
            reasons.append("系统健康等级为危险")

        # 条件 3: 大量退化文件
        if degrading_files and len(degrading_files) >= 3:
            reasons.append(f"{len(degrading_files)} 个文件出现退化迹象")

        # 条件 4: 连续多次回滚后仍然异常
        if recent_rollbacks >= 2:
            reasons.append(f"近期已有 {recent_rollbacks} 次回滚，问题可能更深层")

        if reasons:
            return True, "; ".join(reasons)
        return False, ""

    def get_trend(self) -> HealthTrend:
        """基于历史报告计算当前趋势。"""
        if len(self._report_history) < 2:
            return HealthTrend.STABLE

        recent = self._report_history[-5:]  # 最近 5 次
        scores = [r.overall_score for r in recent]

        first_half_avg = sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
        second_half_avg = sum(scores[len(scores)//2:]) / max(len(scores) - len(scores)//2, 1)

        diff = second_half_avg - first_half_avg

        if diff > 10:
            return HealthTrend.IMPROVING
        elif diff < -10:
            if min(scores) < 30:
                return HealthTrend.CRITICAL
            return HealthTrend.DEGRADING
        return HealthTrend.STABLE

    def get_degrading_files(self, history: list[Any]) -> list[str]:
        """从历史记录中找出越改越坏的文件。"""
        return self._detect_degrading_files(history)

    # ── 维度评分方法 ──────────────────────────────

    def _score_all_dimensions(
        self,
        signals: list[HealthSignal] | None,
        history: list[Any] | None,
        recent_rollbacks: int,
        recent_conflicts: int,
    ) -> list[HealthDimensionScore]:
        """对所有维度进行评分。"""
        signal_map = self._index_signals(signals)

        results: list[HealthDimensionScore] = []
        for dim_name, weight, _label in HEALTH_DIMENSIONS:
            # 延迟构建 scorer lambda，确保闭包能捕获所需变量
            if dim_name == "test_pass_rate":
                scorer = lambda: self._score_test_pass_rate(signal_map)
            elif dim_name == "programming_frequency":
                scorer = lambda: self._score_programming_frequency(signal_map, history)
            elif dim_name == "rollback_rate":
                scorer = lambda: self._score_rollback_rate(recent_rollbacks, history)
            elif dim_name == "conflict_rate":
                scorer = lambda: self._score_conflict_rate(recent_conflicts, history)
            elif dim_name == "file_stability":
                scorer = lambda: self._score_file_stability(history)

            if scorer:
                ds = scorer()
                ds.weighted_score = round(ds.score * weight / 100, 2)
                results.append(ds)
            else:
                results.append(HealthDimensionScore(
                    name=dim_name, score=70.0, weight=weight, weighted_score=round(weight * 0.7, 2),
                ))

        return results

    def _score_test_pass_rate(self, signal_map: dict[str, HealthSignal]) -> HealthDimensionScore:
        """维度 1: 测试通过率（权重 35%）。"""
        sig = signal_map.get("test_pass_rate")
        if sig is not None:
            score = min(sig.value, 100)  # 已经是百分比
            details = (
                f"测试通过率 {sig.value:.1f}%"
                if sig.value >= 80
                else f"⚠️ 测试通过率偏低: {sig.value:.1f}%"
            )
            return HealthDimensionScore(
                name="测试通过率", score=score, weight=35,
                weighted_score=round(score * 35 / 100, 2), details=details,
            )

        return HealthDimensionScore(
            name="测试通过率", score=85.0, weight=35,
            weighted_score=round(85.0 * 35 / 100, 2),
            details="无最新测试数据，假设正常",
        )

    def _score_programming_frequency(
        self,
        signal_map: dict[str, HealthSignal],
        history: list[Any] | None,
    ) -> HealthDimensionScore:
        """维度 2: 自我编程频率（权重 20%）。"""
        sig = signal_map.get("programming_count") or signal_map.get("edit_frequency")
        if sig is not None:
            count = sig.value
            if count <= 1:
                score, detail = 95.0, f"自我编程频率正常 ({count:.1f} 次)"
            elif count <= 3:
                score, detail = 75.0, f"自我编程稍频繁 ({count:.1f} 次)"
            elif count <= 6:
                score, detail = 50.0, f"⚠️ 自我编程频繁 ({count:.1f} 次)，可能不稳定"
            else:
                score, detail = 25.0, f"🔴 自我编程过于频繁 ({count:.1f} 次)，系统可能进入修复循环"
            return HealthDimensionScore(
                name="自我编程频率", score=score, weight=20,
                weighted_score=round(score * 20 / 100, 2),
                details=detail,
            )

        if history:
            count_in_window = len(history)
            if count_in_window <= 2:
                score = 90.0
            elif count_in_window <= 5:
                score = 70.0
            else:
                score = 45.0
            return HealthDimensionScore(
                name="自我编程频率", score=score, weight=20,
                weighted_score=round(score * 20 / 100, 2),
                details=f"最近 {count_in_window} 次自我编程操作",
            )

        return HealthDimensionScore(
            name="自我编程频率", score=85.0, weight=20,
            weighted_score=round(85.0 * 20 / 100, 2),
            details="无频率数据",
        )

    def _score_rollback_rate(
        self,
        recent_rollbacks: int,
        history: list[Any] | None,
    ) -> HealthDimensionScore:
        """维度 3: 近期回滚率（权重 20%）。"""
        total_jobs = len(history) if history else 1

        if total_jobs == 0:
            return HealthDimensionScore(
                name="回滚率", score=100.0, weight=20,
                weighted_score=round(100.0 * 20 / 100, 2),
                details="无历史数据",
            )

        rate = recent_rollbacks / max(total_jobs, 1) * 100

        if recent_rollbacks == 0:
            score, detail = 100.0, "无回滚记录"
        elif rate <= 20:
            score, detail = 80.0, f"回滚率 {rate:.0f}% ({recent_rollbacks}/{total_jobs})"
        elif rate <= 50:
            score, detail = 50.0, f"⚠️ 回滚率偏高: {rate:.0f}%"
        else:
            score, detail = 20.0, f"🔴 回滚率高: {rate:.0f}%，补丁质量堪忧"

        return HealthDimensionScore(
            name="回滚率", score=score, weight=20,
            weighted_score=round(score * 20 / 100, 2),
            details=detail,
        )

    def _score_conflict_rate(
        self,
        recent_conflicts: int,
        history: list[Any] | None,
    ) -> HealthDimensionScore:
        """维度 4: 冲突告警比例（权重 15%）。"""
        total_jobs = len(history) if history else 1

        if recent_conflicts == 0:
            return HealthDimensionScore(
                name="冲突率", score=100.0, weight=15,
                weighted_score=round(100.0 * 15 / 100, 2),
                details="无冲突告警",
            )

        rate = recent_conflicts / max(total_jobs, 1) * 100

        if rate <= 20:
            score, detail = 85.0, f"{recent_conflicts} 次冲突告警"
        elif rate <= 50:
            score, detail = 60.0, f"部分操作有冲突警告 ({recent_conflicts} 次)"
        else:
            score, detail = 30.0, f"大量冲突告警 ({recent_conflicts} 次)"

        return HealthDimensionScore(
            name="冲突率", score=score, weight=15,
            weighted_score=round(score * 15 / 100, 2),
            details=detail,
        )

    def _score_file_stability(self, history: list[Any] | None) -> HealthDimensionScore:
        """维度 5: 文件修改稳定性（权重 10%）。"""
        if not history:
            return HealthDimensionScore(
                name="文件稳定性", score=90.0, weight=10,
                weighted_score=round(90.0 * 10 / 100, 2),
                details="无历史数据",
            )

        file_counts: dict[str, int] = {}
        for entry in history:
            for fp in getattr(entry, 'touched_files', []) or []:
                file_counts[fp] = file_counts.get(fp, 0) + 1

        if not file_counts:
            return HealthDimensionScore(
                name="文件稳定性", score=90.0, weight=10,
                weighted_score=round(90.0 * 10 / 100, 2),
                details="无修改记录",
            )

        max_count = max(file_counts.values())
        most_modified = max(file_counts.items(), key=lambda x: x[1])

        if max_count <= 1:
            score, detail = 95.0, "各文件修改均匀，无明显热点"
        elif max_count <= self.degrading_threshold:
            score, detail = 75.0, f"'{most_modified[0]}' 被修改 {max_count} 次"
        else:
            score, detail = 35.0, f"🔴 '{most_modified[0]}' 被修改 {max_count} 次，可能存在循环修复"

        return HealthDimensionScore(
            name="文件稳定性", score=score, weight=10,
            weighted_score=round(score * 10 / 100, 2),
            details=detail,
        )

    # ── 内部工具方法 ──────────────────────────────

    @staticmethod
    def _index_signals(signals: list[HealthSignal] | None) -> dict[str, HealthSignal]:
        """将信号列表按 metric 名索引。"""
        if not signals:
            return {}
        return {s.metric: s for s in signals}

    @staticmethod
    def _score_to_grade(score: float) -> HealthGrade:
        """将分数映射为等级。"""
        if score >= 90:
            return HealthGrade.EXCELLENT
        if score >= 75:
            return HealthGrade.GOOD
        if score >= 60:
            return HealthGrade.FAIR
        if score >= 40:
            return HealthGrade.POOR
        return HealthGrade.CRITICAL

    def _detect_degrading_files(self, history: list[Any]) -> list[str]:
        """检测出修改频率过高的文件。"""
        if not history:
            return []

        file_counts: dict[str, int] = {}
        for entry in history:
            for fp in getattr(entry, 'touched_files', []) or []:
                file_counts[fp] = file_counts.get(fp, 0) + 1

        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return [fp for fp, cnt in sorted_files if cnt >= self.degrading_threshold]

    def _generate_recommendations(
        self,
        overall: float,
        dimensions: list[HealthDimensionScore],
        degrading_files: list[str],
    ) -> list[str]:
        """根据评分生成改进建议。"""
        recs: list[str] = []

        if overall >= 90:
            recs.append("系统运行良好，继续保持。")
        elif overall >= 75:
            recs.append("整体健康状况良好，关注低分维度的优化空间。")
        elif overall >= 60:
            recs.append("存在一些健康隐患，建议排查具体原因。")
        elif overall >= 40:
            recs.append("⚠️ 健康状况较差，强烈建议审查最近的改动。")
        else:
            recs.append("🔴 系统健康危急，建议立即回滚最近的自我编程操作。")

        low_dims = [d for d in dimensions if d.score < 60]
        for d in low_dims[:3]:
            if d.name == "测试通过率":
                recs.append(f"• 测试通过率偏低({d.score:.0f})：检查是否有回归问题")
            elif d.name == "自我编程频率":
                recs.append(f"• 自我编程过于频繁({d.score:.0f})：考虑增加冷却时间")
            elif d.name == "回滚率":
                recs.append(f"• 回滚率较高({d.score:.0f})：说明补丁质量需要提升")
            elif d.name == "冲突率":
                recs.append(f"• 冲突较多({d.score:.0f})：注意并行任务间的协调")
            elif d.name == "文件稳定性":
                recs.append(f"• 文件不稳定({d.score:.0f})：某些文件被反复修改")

        if degrading_files:
            recs.append(
                f"• 以下文件可能存在循环修复问题: {', '.join(degrading_files[:5])}"
            )

        return recs

    def _compute_trend(self, current_score: float) -> HealthTrend:
        """基于当前分数和历史计算趋势。"""
        if len(self._report_history) < 3:
            return HealthTrend.STABLE

        recent_scores = [r.overall_score for r in self._report_history[-5:]]
        avg_recent = sum(recent_scores) / len(recent_scores)
        diff = current_score - avg_recent

        if diff > 15:
            return HealthTrend.IMPROVING
        elif diff < -15:
            if current_score < 30:
                return HealthTrend.CRITICAL
            return HealthTrend.DEGRADING
        return HealthTrend.STABLE
