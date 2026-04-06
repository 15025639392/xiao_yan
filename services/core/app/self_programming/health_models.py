"""
自我编程健康检查的数据模型与维度定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


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
    """单个健康信号。"""

    source: str
    metric: str
    value: float
    unit: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", datetime.now(timezone.utc).isoformat())


@dataclass
class HealthDimensionScore:
    """单个维度评分详情。"""

    name: str
    score: float
    weight: float
    weighted_score: float
    details: str = ""

    @property
    def display(self) -> str:
        return f"{self.name}: {self.score:.0f}/100 (×{self.weight}) = {self.weighted_score:.1f}"


@dataclass
class HealthReport:
    """完整健康报告。"""

    overall_score: float
    grade: HealthGrade
    trend: HealthTrend = HealthTrend.STABLE
    dimensions: list[HealthDimensionScore] = field(default_factory=list)
    signals_used: list[HealthSignal] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    degrading_files: list[str] = field(default_factory=list)
    rollback_advised: bool = False
    rollback_reason: str = ""
    generated_at: str = ""
    window_seconds: float = 3600

    def __post_init__(self) -> None:
        if not self.generated_at:
            object.__setattr__(self, "generated_at", datetime.now(timezone.utc).isoformat())

    @property
    def summary(self) -> str:
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


# (名称, 权重, 描述)
HEALTH_DIMENSIONS = [
    ("test_pass_rate", 35, "测试通过率"),
    ("programming_frequency", 20, "自我编程频率"),
    ("rollback_rate", 20, "近期回滚率"),
    ("conflict_rate", 15, "冲突告警比例"),
    ("file_stability", 10, "文件修改稳定性"),
]


__all__ = [
    "HealthTrend",
    "HealthGrade",
    "HealthSignal",
    "HealthDimensionScore",
    "HealthReport",
    "HEALTH_DIMENSIONS",
]
