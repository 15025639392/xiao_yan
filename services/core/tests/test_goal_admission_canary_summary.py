from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "tools" / "goal_admission" / "goal_admission_canary_summary.py"


def _write_stats(path: Path, *, admit: int, defer: int, drop: int, wip_blocked: int, queue: int) -> None:
    payload = {
        "mode": "enforce",
        "today": {
            "admit": admit,
            "defer": defer,
            "drop": drop,
            "wip_blocked": wip_blocked,
        },
        "deferred_queue_size": queue,
        "thresholds": {
            "user_topic": {"min_score": 0.68, "defer_score": 0.45},
            "world_event": {"min_score": 0.75, "defer_score": 0.52},
            "chain_next": {"min_score": 0.62, "defer_score": 0.45},
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_canary_summary_script_generates_report_and_hold_recommendation(tmp_path: Path):
    canary_dir = tmp_path / "canary"
    canary_dir.mkdir(parents=True, exist_ok=True)
    _write_stats(canary_dir / "stats-01.json", admit=10, defer=5, drop=2, wip_blocked=1, queue=3)
    _write_stats(canary_dir / "stats-02.json", admit=14, defer=7, drop=3, wip_blocked=1, queue=3)
    _write_stats(canary_dir / "stats-03.json", admit=18, defer=9, drop=4, wip_blocked=2, queue=2)

    report_path = tmp_path / "canary-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--input-dir",
            str(canary_dir),
            "--output",
            str(report_path),
            "--baseline-drop-rate",
            "0.1",
            "--baseline-wip-blocked-rate",
            "0.04",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(payload["samples"]) == 3
    assert payload["summary"]["sample_count"] == 3
    assert payload["recommendation"]["status"] in {"hold", "promote"}
    assert "reason" in payload["recommendation"]


def test_canary_summary_script_flags_queue_growth_as_rollback(tmp_path: Path):
    canary_dir = tmp_path / "canary"
    canary_dir.mkdir(parents=True, exist_ok=True)
    _write_stats(canary_dir / "stats-01.json", admit=10, defer=5, drop=1, wip_blocked=0, queue=1)
    _write_stats(canary_dir / "stats-02.json", admit=12, defer=7, drop=1, wip_blocked=0, queue=2)
    _write_stats(canary_dir / "stats-03.json", admit=14, defer=9, drop=1, wip_blocked=0, queue=3)

    report_path = tmp_path / "canary-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--input-dir",
            str(canary_dir),
            "--output",
            str(report_path),
            "--baseline-drop-rate",
            "0.1",
            "--baseline-wip-blocked-rate",
            "0.05",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["recommendation"]["status"] == "rollback"
    assert "queue_growth" in payload["recommendation"]["triggered_by"]
