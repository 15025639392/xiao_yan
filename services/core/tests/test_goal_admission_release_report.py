from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "goal_admission_release_report.py"


def _write_replay_report(path: Path) -> None:
    payload = {
        "generated_at": "2026-04-08T10:00:00+00:00",
        "baseline": {
            "phase3_ready": False,
            "config": {
                "min_score": 0.68,
                "defer_score": 0.45,
                "world_min_score": 0.75,
                "world_defer_score": 0.52,
                "chain_min_score": 0.62,
                "chain_defer_score": 0.45,
            },
            "stats": {
                "today": {"admit": 40, "defer": 22, "drop": 18, "wip_blocked": 5},
                "deferred_queue_size": 9,
            },
        },
        "candidate": {
            "phase3_ready": True,
            "config": {
                "min_score": 0.72,
                "defer_score": 0.50,
                "world_min_score": 0.78,
                "world_defer_score": 0.55,
                "chain_min_score": 0.66,
                "chain_defer_score": 0.46,
            },
            "stats": {
                "today": {"admit": 36, "defer": 24, "drop": 20, "wip_blocked": 4},
                "deferred_queue_size": 7,
            },
        },
        "comparison": {
            "delta_today": {"admit": -4, "defer": 2, "drop": 2, "wip_blocked": -1},
            "delta_deferred_queue_size": -2,
            "recommendation": {
                "status": "promote_candidate",
                "reason": "candidate reaches readiness while baseline does not",
            },
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_canary_summary(path: Path) -> None:
    payload = {
        "generated_at": "2026-04-08T11:00:00+00:00",
        "summary": {
            "sample_count": 12,
            "baseline_drop_rate": 0.10,
            "baseline_wip_blocked_rate": 0.04,
            "max_queue_rising_streak": 1,
            "max_drop_rate_increase_ratio": 0.15,
            "max_wip_blocked_rate_increase_ratio": 0.12,
        },
        "recommendation": {
            "status": "promote",
            "reason": "healthy canary streak reached promote threshold",
            "triggered_by": [],
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_release_report_script_generates_markdown_with_decision(tmp_path: Path):
    replay_path = tmp_path / "replay.json"
    canary_path = tmp_path / "canary-summary.json"
    output_path = tmp_path / "release-report.md"
    _write_replay_report(replay_path)
    _write_canary_summary(canary_path)

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--replay-report",
            str(replay_path),
            "--canary-summary",
            str(canary_path),
            "--output",
            str(output_path),
            "--owner-engineering",
            "alice",
            "--owner-product",
            "bob",
            "--owner-oncall",
            "carol",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Goal Admission Phase 3 发布报告" in content
    assert "alice" in content
    assert "bob" in content
    assert "carol" in content
    assert "promote_candidate" in content
    assert "promote" in content
    assert "最终建议：可以放量" in content


def test_release_report_script_requires_existing_inputs(tmp_path: Path):
    output_path = tmp_path / "release-report.md"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--replay-report",
            str(tmp_path / "missing-replay.json"),
            "--canary-summary",
            str(tmp_path / "missing-canary.json"),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "not found" in combined
