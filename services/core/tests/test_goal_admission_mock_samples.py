from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "tools" / "goal_admission" / "goal_admission_mock_samples.py"


def test_mock_samples_script_generates_requested_count_and_shape(tmp_path: Path):
    output_dir = tmp_path / "mock-samples"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--output-dir",
            str(output_dir),
            "--count",
            "6",
            "--scenario",
            "healthy",
            "--seed",
            "11",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    files = sorted(output_dir.glob("stats-*.json"))
    assert len(files) == 6

    sample = json.loads(files[0].read_text(encoding="utf-8"))
    assert sample["mode"] == "enforce"
    assert set(("admit", "defer", "drop", "wip_blocked")).issubset(sample["today"].keys())
    assert "deferred_queue_size" in sample


def test_mock_samples_script_queue_growth_scenario_is_monotonic(tmp_path: Path):
    output_dir = tmp_path / "mock-samples"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--output-dir",
            str(output_dir),
            "--count",
            "5",
            "--scenario",
            "queue_growth",
            "--seed",
            "12",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    files = sorted(output_dir.glob("stats-*.json"))
    queues = [json.loads(path.read_text(encoding="utf-8"))["deferred_queue_size"] for path in files]
    assert queues == sorted(queues)
    assert len(set(queues)) > 1


def test_mock_samples_script_rejects_invalid_count(tmp_path: Path):
    output_dir = tmp_path / "mock-samples"
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--output-dir",
            str(output_dir),
            "--count",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "count" in combined
