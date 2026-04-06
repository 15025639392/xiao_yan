"""
自我编程历史统计纯函数。
"""

from __future__ import annotations

from typing import Any

from app.self_programming.history_models import HistoryEntry, HistoryEntryStatus


def build_history_statistics(all_entries: list[HistoryEntry]) -> dict[str, Any]:
    total = len(all_entries)
    applied = sum(1 for e in all_entries if e.status == HistoryEntryStatus.APPLIED)
    failed = sum(1 for e in all_entries if e.status == HistoryEntryStatus.FAILED)

    area_counts: dict[str, int] = {}
    for entry in all_entries:
        area_counts[entry.target_area] = area_counts.get(entry.target_area, 0) + 1

    file_counts: dict[str, int] = {}
    for entry in all_entries:
        for file_path in entry.touched_files:
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
    top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    sandbox_used = sum(1 for e in all_entries if e.sandbox_prevalidated)
    sandbox_rate = sandbox_used / total * 100 if total > 0 else 0.0

    conflict_count = sum(1 for e in all_entries if e.conflict_count > 0)
    conflict_rate = conflict_count / total * 100 if total > 0 else 0.0

    return {
        "total_jobs": total,
        "applied": applied,
        "failed": failed,
        "success_rate": round(applied / total * 100, 1) if total > 0 else 0.0,
        "by_target_area": area_counts,
        "most_modified_files": top_files,
        "sandbox_usage_rate": round(sandbox_rate, 1),
        "conflict_alert_rate": round(conflict_rate, 1),
        "multi_candidate_usage": sum(1 for e in all_entries if e.candidates_tried > 1),
    }


__all__ = [
    "build_history_statistics",
]
