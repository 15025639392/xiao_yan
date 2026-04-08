#!/usr/bin/env python3
"""One-command canary pipeline: collect -> summarize -> release report."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


REPO_CORE = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_stats(api_base_url: str, timeout_seconds: int) -> dict:
    url = f"{api_base_url.rstrip('/')}/goals/admission/stats"
    request = Request(url=url, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _write_sample(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _collect_from_source(sample_source_dir: Path, sample_count: int, canary_dir: Path) -> None:
    source_files = sorted(sample_source_dir.glob("*.json"))
    if len(source_files) < sample_count:
        raise ValueError("insufficient sample source files for requested sample-count")

    for index, source_path in enumerate(source_files[:sample_count], start=1):
        target_path = canary_dir / f"stats-{index:02d}.json"
        shutil.copy2(source_path, target_path)


def _collect_from_api(
    *,
    api_base_url: str,
    sample_count: int,
    interval_seconds: int,
    timeout_seconds: int,
    canary_dir: Path,
) -> None:
    for index in range(1, sample_count + 1):
        payload = _fetch_stats(api_base_url, timeout_seconds=timeout_seconds)
        target_path = canary_dir / f"stats-{index:02d}.json"
        _write_sample(target_path, payload)
        if index < sample_count and interval_seconds > 0:
            time.sleep(interval_seconds)


def _derive_baselines_from_replay(replay_report: dict) -> tuple[float, float]:
    today = replay_report.get("baseline", {}).get("stats", {}).get("today", {})
    admit = int(today.get("admit", 0))
    defer = int(today.get("defer", 0))
    drop = int(today.get("drop", 0))
    wip_blocked = int(today.get("wip_blocked", 0))
    total = admit + defer + drop
    if total <= 0:
        return 0.0, 0.0
    return drop / total, wip_blocked / total


def _run_script(script_name: str, args: list[str]) -> None:
    cmd = [sys.executable, str(REPO_CORE / "scripts" / script_name), *args]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{script_name} failed: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run canary collection and reporting in one command.")
    parser.add_argument("--replay-report", type=str, required=True)
    parser.add_argument("--canary-dir", type=str, required=True)
    parser.add_argument("--canary-summary-output", type=str, required=True)
    parser.add_argument("--release-report-output", type=str, required=True)

    parser.add_argument("--sample-source-dir", type=str, default="")
    parser.add_argument("--sample-count", type=int, default=12)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--api-base-url", type=str, default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-seconds", type=int, default=10)

    parser.add_argument("--baseline-drop-rate", type=float, default=None)
    parser.add_argument("--baseline-wip-blocked-rate", type=float, default=None)

    parser.add_argument("--owner-engineering", type=str, default="TBD")
    parser.add_argument("--owner-product", type=str, default="TBD")
    parser.add_argument("--owner-oncall", type=str, default="TBD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    replay_path = Path(args.replay_report).expanduser()
    canary_dir = Path(args.canary_dir).expanduser()
    canary_summary_output = Path(args.canary_summary_output).expanduser()
    release_output = Path(args.release_report_output).expanduser()
    sample_count = max(1, int(args.sample_count))
    interval_seconds = max(0, int(args.interval_seconds))
    timeout_seconds = max(1, int(args.timeout_seconds))

    if not replay_path.exists():
        print(f"replay report not found: {replay_path}")
        return 2

    replay_report = _load_json(replay_path)
    canary_dir.mkdir(parents=True, exist_ok=True)

    sample_source_dir = Path(args.sample_source_dir).expanduser() if args.sample_source_dir else None
    try:
        if sample_source_dir is not None:
            if not sample_source_dir.exists() or not sample_source_dir.is_dir():
                print(f"sample source dir not found: {sample_source_dir}")
                return 2
            _collect_from_source(sample_source_dir, sample_count=sample_count, canary_dir=canary_dir)
        else:
            _collect_from_api(
                api_base_url=args.api_base_url,
                sample_count=sample_count,
                interval_seconds=interval_seconds,
                timeout_seconds=timeout_seconds,
                canary_dir=canary_dir,
            )
    except ValueError as error:
        print(str(error))
        return 2
    except URLError as error:
        print(f"failed to fetch admission stats: {error}")
        return 2

    baseline_drop_rate, baseline_wip_rate = _derive_baselines_from_replay(replay_report)
    if args.baseline_drop_rate is not None:
        baseline_drop_rate = float(args.baseline_drop_rate)
    if args.baseline_wip_blocked_rate is not None:
        baseline_wip_rate = float(args.baseline_wip_blocked_rate)

    try:
        _run_script(
            "goal_admission_canary_summary.py",
            [
                "--input-dir",
                str(canary_dir),
                "--baseline-drop-rate",
                str(baseline_drop_rate),
                "--baseline-wip-blocked-rate",
                str(baseline_wip_rate),
                "--output",
                str(canary_summary_output),
            ],
        )
        _run_script(
            "goal_admission_release_report.py",
            [
                "--replay-report",
                str(replay_path),
                "--canary-summary",
                str(canary_summary_output),
                "--output",
                str(release_output),
                "--owner-engineering",
                args.owner_engineering,
                "--owner-product",
                args.owner_product,
                "--owner-oncall",
                args.owner_oncall,
            ],
        )
    except RuntimeError as error:
        print(str(error))
        return 2

    print("Goal admission canary pipeline finished")
    print(f"- sample_count: {sample_count}")
    print(f"- canary_dir: {canary_dir}")
    print(f"- canary_summary: {canary_summary_output}")
    print(f"- release_report: {release_output}")
    print(f"- generated_at: {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
