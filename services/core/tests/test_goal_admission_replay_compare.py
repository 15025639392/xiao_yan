from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "tools" / "goal_admission" / "goal_admission_replay_compare.py"


def test_replay_compare_script_generates_structured_report_with_required_metrics(tmp_path: Path):
    report_path = tmp_path / "goal-admission-replay-report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--iterations",
            "120",
            "--seed",
            "7",
            "--candidate-min-score",
            "0.74",
            "--candidate-defer-score",
            "0.5",
            "--output",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert report_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert "baseline" in payload
    assert "candidate" in payload
    assert "comparison" in payload

    for side in ("baseline", "candidate"):
        assert "stats" in payload[side]
        today = payload[side]["stats"]["today"]
        assert set(("admit", "defer", "drop", "wip_blocked")).issubset(today.keys())
        assert "deferred_queue_size" in payload[side]["stats"]

    delta_today = payload["comparison"]["delta_today"]
    assert set(("admit", "defer", "drop", "wip_blocked")).issubset(delta_today.keys())
    assert "delta_deferred_queue_size" in payload["comparison"]
    assert "recommendation" in payload["comparison"]


def test_replay_compare_script_requires_candidate_overrides():
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--iterations",
            "50",
            "--seed",
            "8",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "candidate" in combined.lower()
