from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "goal_admission_canary_pipeline.py"


def _write_replay_report(path: Path) -> None:
    payload = {
        "baseline": {
            "stats": {
                "today": {"admit": 40, "defer": 20, "drop": 10, "wip_blocked": 3},
            },
            "config": {
                "min_score": 0.68,
                "defer_score": 0.45,
                "world_min_score": 0.75,
                "world_defer_score": 0.52,
                "chain_min_score": 0.62,
                "chain_defer_score": 0.45,
            },
        },
        "candidate": {
            "config": {
                "min_score": 0.72,
                "defer_score": 0.50,
                "world_min_score": 0.78,
                "world_defer_score": 0.55,
                "chain_min_score": 0.66,
                "chain_defer_score": 0.46,
            },
        },
        "comparison": {
            "recommendation": {
                "status": "promote_candidate",
                "reason": "candidate reaches readiness while baseline does not",
            }
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_canary_pipeline_script_runs_end_to_end_with_sample_source(tmp_path: Path):
    replay_path = tmp_path / "replay.json"
    _write_replay_report(replay_path)

    sample_source = tmp_path / "sample-source"
    sample_source.mkdir(parents=True, exist_ok=True)
    _write_stats(sample_source / "stats-01.json", admit=10, defer=5, drop=1, wip_blocked=0, queue=2)
    _write_stats(sample_source / "stats-02.json", admit=12, defer=6, drop=1, wip_blocked=0, queue=2)
    _write_stats(sample_source / "stats-03.json", admit=14, defer=7, drop=1, wip_blocked=0, queue=1)

    canary_dir = tmp_path / "canary"
    summary_path = tmp_path / "canary-summary.json"
    release_path = tmp_path / "release-report.md"

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--replay-report",
            str(replay_path),
            "--sample-source-dir",
            str(sample_source),
            "--sample-count",
            "3",
            "--interval-seconds",
            "0",
            "--canary-dir",
            str(canary_dir),
            "--canary-summary-output",
            str(summary_path),
            "--release-report-output",
            str(release_path),
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
    assert canary_dir.exists()
    assert len(list(canary_dir.glob("stats-*.json"))) == 3
    assert summary_path.exists()
    assert release_path.exists()
    assert "最终建议：可以放量" in release_path.read_text(encoding="utf-8")


def test_canary_pipeline_script_rejects_insufficient_sample_source(tmp_path: Path):
    replay_path = tmp_path / "replay.json"
    _write_replay_report(replay_path)

    sample_source = tmp_path / "sample-source"
    sample_source.mkdir(parents=True, exist_ok=True)
    _write_stats(sample_source / "stats-01.json", admit=10, defer=5, drop=1, wip_blocked=0, queue=2)

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--replay-report",
            str(replay_path),
            "--sample-source-dir",
            str(sample_source),
            "--sample-count",
            "3",
            "--canary-dir",
            str(tmp_path / "canary"),
            "--canary-summary-output",
            str(tmp_path / "canary-summary.json"),
            "--release-report-output",
            str(tmp_path / "release-report.md"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "insufficient" in combined
