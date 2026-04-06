"""
自我编程健康检查的评分与趋势纯函数。
"""

from __future__ import annotations

from typing import Any

from app.self_programming.health_models import (
    HealthDimensionScore,
    HealthGrade,
    HealthReport,
    HealthSignal,
    HealthTrend,
)


def index_signals(signals: list[HealthSignal] | None) -> dict[str, HealthSignal]:
    if not signals:
        return {}
    return {s.metric: s for s in signals}


def score_to_grade(score: float) -> HealthGrade:
    if score >= 90:
        return HealthGrade.EXCELLENT
    if score >= 75:
        return HealthGrade.GOOD
    if score >= 60:
        return HealthGrade.FAIR
    if score >= 40:
        return HealthGrade.POOR
    return HealthGrade.CRITICAL


def score_test_pass_rate(signal_map: dict[str, HealthSignal]) -> HealthDimensionScore:
    sig = signal_map.get("test_pass_rate")
    if sig is not None:
        score = min(sig.value, 100)
        details = (
            f"测试通过率 {sig.value:.1f}%"
            if sig.value >= 80
            else f"⚠️ 测试通过率偏低: {sig.value:.1f}%"
        )
        return HealthDimensionScore(
            name="测试通过率",
            score=score,
            weight=35,
            weighted_score=round(score * 35 / 100, 2),
            details=details,
        )

    return HealthDimensionScore(
        name="测试通过率",
        score=85.0,
        weight=35,
        weighted_score=round(85.0 * 35 / 100, 2),
        details="无最新测试数据，假设正常",
    )


def score_programming_frequency(
    signal_map: dict[str, HealthSignal],
    history: list[Any] | None,
) -> HealthDimensionScore:
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
            name="自我编程频率",
            score=score,
            weight=20,
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
            name="自我编程频率",
            score=score,
            weight=20,
            weighted_score=round(score * 20 / 100, 2),
            details=f"最近 {count_in_window} 次自我编程操作",
        )

    return HealthDimensionScore(
        name="自我编程频率",
        score=85.0,
        weight=20,
        weighted_score=round(85.0 * 20 / 100, 2),
        details="无频率数据",
    )


def score_rollback_rate(
    recent_rollbacks: int,
    history: list[Any] | None,
) -> HealthDimensionScore:
    total_jobs = len(history) if history else 1

    if total_jobs == 0:
        return HealthDimensionScore(
            name="回滚率",
            score=100.0,
            weight=20,
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
        name="回滚率",
        score=score,
        weight=20,
        weighted_score=round(score * 20 / 100, 2),
        details=detail,
    )


def score_conflict_rate(
    recent_conflicts: int,
    history: list[Any] | None,
) -> HealthDimensionScore:
    total_jobs = len(history) if history else 1

    if recent_conflicts == 0:
        return HealthDimensionScore(
            name="冲突率",
            score=100.0,
            weight=15,
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
        name="冲突率",
        score=score,
        weight=15,
        weighted_score=round(score * 15 / 100, 2),
        details=detail,
    )


def score_file_stability(
    history: list[Any] | None,
    degrading_threshold: int,
) -> HealthDimensionScore:
    if not history:
        return HealthDimensionScore(
            name="文件稳定性",
            score=90.0,
            weight=10,
            weighted_score=round(90.0 * 10 / 100, 2),
            details="无历史数据",
        )

    file_counts: dict[str, int] = {}
    for entry in history:
        for fp in getattr(entry, "touched_files", []) or []:
            file_counts[fp] = file_counts.get(fp, 0) + 1

    if not file_counts:
        return HealthDimensionScore(
            name="文件稳定性",
            score=90.0,
            weight=10,
            weighted_score=round(90.0 * 10 / 100, 2),
            details="无修改记录",
        )

    max_count = max(file_counts.values())
    most_modified = max(file_counts.items(), key=lambda x: x[1])

    if max_count <= 1:
        score, detail = 95.0, "各文件修改均匀，无明显热点"
    elif max_count <= degrading_threshold:
        score, detail = 75.0, f"'{most_modified[0]}' 被修改 {max_count} 次"
    else:
        score, detail = 35.0, f"🔴 '{most_modified[0]}' 被修改 {max_count} 次，可能存在循环修复"

    return HealthDimensionScore(
        name="文件稳定性",
        score=score,
        weight=10,
        weighted_score=round(score * 10 / 100, 2),
        details=detail,
    )


def score_dimension(
    *,
    dim_name: str,
    weight: int,
    signal_map: dict[str, HealthSignal],
    history: list[Any] | None,
    recent_rollbacks: int,
    recent_conflicts: int,
    degrading_threshold: int,
) -> HealthDimensionScore:
    if dim_name == "test_pass_rate":
        return score_test_pass_rate(signal_map)
    if dim_name == "programming_frequency":
        return score_programming_frequency(signal_map, history)
    if dim_name == "rollback_rate":
        return score_rollback_rate(recent_rollbacks, history)
    if dim_name == "conflict_rate":
        return score_conflict_rate(recent_conflicts, history)
    if dim_name == "file_stability":
        return score_file_stability(history, degrading_threshold)

    return HealthDimensionScore(
        name=dim_name,
        score=70.0,
        weight=weight,
        weighted_score=round(weight * 0.7, 2),
    )


def detect_degrading_files(
    history: list[Any] | None,
    degrading_threshold: int,
) -> list[str]:
    if not history:
        return []

    file_counts: dict[str, int] = {}
    for entry in history:
        for fp in getattr(entry, "touched_files", []) or []:
            file_counts[fp] = file_counts.get(fp, 0) + 1

    sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
    return [fp for fp, cnt in sorted_files if cnt >= degrading_threshold]


def generate_recommendations(
    overall: float,
    dimensions: list[HealthDimensionScore],
    degrading_files: list[str],
) -> list[str]:
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


def compute_history_trend(report_history: list[HealthReport]) -> HealthTrend:
    if len(report_history) < 2:
        return HealthTrend.STABLE

    recent = report_history[-5:]
    scores = [r.overall_score for r in recent]

    first_half_avg = sum(scores[: len(scores) // 2]) / max(len(scores) // 2, 1)
    second_half_avg = sum(scores[len(scores) // 2 :]) / max(len(scores) - len(scores) // 2, 1)

    diff = second_half_avg - first_half_avg

    if diff > 10:
        return HealthTrend.IMPROVING
    if diff < -10:
        if min(scores) < 30:
            return HealthTrend.CRITICAL
        return HealthTrend.DEGRADING
    return HealthTrend.STABLE


def compute_current_trend(
    current_score: float,
    report_history: list[HealthReport],
) -> HealthTrend:
    if len(report_history) < 3:
        return HealthTrend.STABLE

    recent_scores = [r.overall_score for r in report_history[-5:]]
    avg_recent = sum(recent_scores) / len(recent_scores)
    diff = current_score - avg_recent

    if diff > 15:
        return HealthTrend.IMPROVING
    if diff < -15:
        if current_score < 30:
            return HealthTrend.CRITICAL
        return HealthTrend.DEGRADING
    return HealthTrend.STABLE


__all__ = [
    "index_signals",
    "score_to_grade",
    "score_test_pass_rate",
    "score_programming_frequency",
    "score_rollback_rate",
    "score_conflict_rate",
    "score_file_stability",
    "score_dimension",
    "detect_degrading_files",
    "generate_recommendations",
    "compute_history_trend",
    "compute_current_trend",
]
