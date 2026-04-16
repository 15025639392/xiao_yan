#!/usr/bin/env python3
"""Summarize canary stats snapshots and produce promote/rollback recommendation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from math import ceil
from pathlib import Path


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _increase_ratio(current: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0 if current <= 0 else float("inf")
    return (current - baseline) / baseline


def _load_sample(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    today = payload.get("today", {})
    admit = int(today.get("admit", 0))
    defer = int(today.get("defer", 0))
    drop = int(today.get("drop", 0))
    wip_blocked = int(today.get("wip_blocked", 0))
    total = admit + defer + drop
    queue = int(payload.get("deferred_queue_size", 0))
    return {
        "file": str(path),
        "admit": admit,
        "defer": defer,
        "drop": drop,
        "wip_blocked": wip_blocked,
        "total": total,
        "deferred_queue_size": queue,
        "drop_rate": _safe_rate(drop, total),
        "wip_blocked_rate": _safe_rate(wip_blocked, total),
    }


def _collect_samples(input_dir: Path) -> list[dict]:
    files = sorted(input_dir.glob("*.json"))
    samples = [_load_sample(path) for path in files]
    if not samples:
        raise ValueError("no canary stats json files found in input directory")
    return samples


def _build_enriched_samples(
    samples: list[dict],
    *,
    baseline_drop_rate: float,
    baseline_wip_blocked_rate: float,
) -> tuple[list[dict], int]:
    enriched: list[dict] = []
    queue_rising_streak = 1
    prev_queue: int | None = None
    max_queue_rising_streak = 0

    for sample in samples:
        queue = int(sample["deferred_queue_size"])
        queue_delta = 0 if prev_queue is None else queue - prev_queue
        queue_rising = prev_queue is not None and queue > prev_queue
        if prev_queue is None:
            queue_rising_streak = 1
        elif queue_rising:
            queue_rising_streak += 1
        else:
            queue_rising_streak = 1
        max_queue_rising_streak = max(max_queue_rising_streak, queue_rising_streak)

        drop_increase_ratio = _increase_ratio(float(sample["drop_rate"]), baseline_drop_rate)
        wip_increase_ratio = _increase_ratio(float(sample["wip_blocked_rate"]), baseline_wip_blocked_rate)

        enriched.append(
            {
                **sample,
                "queue_delta": queue_delta,
                "queue_rising": queue_rising,
                "queue_rising_streak": queue_rising_streak,
                "drop_rate_increase_ratio": drop_increase_ratio,
                "wip_blocked_rate_increase_ratio": wip_increase_ratio,
            }
        )
        prev_queue = queue

    return enriched, max_queue_rising_streak


def _tail_streak(samples: list[dict], predicate) -> int:
    streak = 0
    for sample in reversed(samples):
        if predicate(sample):
            streak += 1
        else:
            break
    return streak


def _max_streak(samples: list[dict], predicate) -> int:
    best = 0
    current = 0
    for sample in samples:
        if predicate(sample):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _build_recommendation(
    samples: list[dict],
    *,
    promote_drop_increase_limit: float,
    promote_wip_increase_limit: float,
    rollback_drop_increase_limit: float,
    rollback_wip_increase_limit: float,
    rollback_queue_rising_streak: int,
    rollback_breach_streak: int,
    promote_healthy_streak: int,
) -> dict:
    queue_growth_trigger = any(int(item["queue_rising_streak"]) >= rollback_queue_rising_streak for item in samples)
    drop_breach = _max_streak(samples, lambda item: float(item["drop_rate_increase_ratio"]) > rollback_drop_increase_limit)
    wip_breach = _max_streak(samples, lambda item: float(item["wip_blocked_rate_increase_ratio"]) > rollback_wip_increase_limit)
    drop_trigger = drop_breach >= rollback_breach_streak
    wip_trigger = wip_breach >= rollback_breach_streak

    triggered_by: list[str] = []
    if queue_growth_trigger:
        triggered_by.append("queue_growth")
    if drop_trigger:
        triggered_by.append("drop_rate")
    if wip_trigger:
        triggered_by.append("wip_blocked_rate")

    if triggered_by:
        return {
            "status": "rollback",
            "reason": "rollback triggers hit during canary",
            "triggered_by": triggered_by,
        }

    healthy_tail = _tail_streak(
        samples,
        lambda item: (
            not bool(item["queue_rising"])
            and float(item["drop_rate_increase_ratio"]) <= promote_drop_increase_limit
            and float(item["wip_blocked_rate_increase_ratio"]) <= promote_wip_increase_limit
        ),
    )
    if healthy_tail >= promote_healthy_streak:
        return {
            "status": "promote",
            "reason": "healthy canary streak reached promote threshold",
            "triggered_by": [],
        }

    return {
        "status": "hold",
        "reason": "canary is stable but promote streak is not enough yet",
        "triggered_by": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize goal-admission canary stats snapshots.")
    parser.add_argument("--input-dir", type=str, required=True, help="Directory containing canary stats json files.")
    parser.add_argument("--output", type=str, default="", help="Optional output path for summary report JSON.")
    parser.add_argument("--print-json", action="store_true")

    parser.add_argument("--baseline-drop-rate", type=float, default=None)
    parser.add_argument("--baseline-wip-blocked-rate", type=float, default=None)

    parser.add_argument("--sample-interval-minutes", type=int, default=5)
    parser.add_argument("--rollback-sustained-minutes", type=int, default=15)
    parser.add_argument("--rollback-queue-rising-streak", type=int, default=3)

    parser.add_argument("--promote-drop-increase-limit", type=float, default=0.20)
    parser.add_argument("--promote-wip-increase-limit", type=float, default=0.20)
    parser.add_argument("--rollback-drop-increase-limit", type=float, default=0.30)
    parser.add_argument("--rollback-wip-increase-limit", type=float, default=0.30)
    parser.add_argument("--promote-healthy-streak", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser()
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"input directory not found: {input_dir}")

    try:
        raw_samples = _collect_samples(input_dir)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    baseline_drop_rate = (
        float(args.baseline_drop_rate)
        if args.baseline_drop_rate is not None
        else float(raw_samples[0]["drop_rate"])
    )
    baseline_wip_blocked_rate = (
        float(args.baseline_wip_blocked_rate)
        if args.baseline_wip_blocked_rate is not None
        else float(raw_samples[0]["wip_blocked_rate"])
    )

    samples, max_queue_rising_streak = _build_enriched_samples(
        raw_samples,
        baseline_drop_rate=baseline_drop_rate,
        baseline_wip_blocked_rate=baseline_wip_blocked_rate,
    )

    rollback_breach_streak = max(
        1,
        ceil(
            max(1, int(args.rollback_sustained_minutes))
            / max(1, int(args.sample_interval_minutes))
        ),
    )

    recommendation = _build_recommendation(
        samples,
        promote_drop_increase_limit=float(args.promote_drop_increase_limit),
        promote_wip_increase_limit=float(args.promote_wip_increase_limit),
        rollback_drop_increase_limit=float(args.rollback_drop_increase_limit),
        rollback_wip_increase_limit=float(args.rollback_wip_increase_limit),
        rollback_queue_rising_streak=max(1, int(args.rollback_queue_rising_streak)),
        rollback_breach_streak=rollback_breach_streak,
        promote_healthy_streak=max(1, int(args.promote_healthy_streak)),
    )

    summary = {
        "sample_count": len(samples),
        "baseline_drop_rate": baseline_drop_rate,
        "baseline_wip_blocked_rate": baseline_wip_blocked_rate,
        "max_queue_rising_streak": max_queue_rising_streak,
        "max_drop_rate_increase_ratio": max(float(item["drop_rate_increase_ratio"]) for item in samples),
        "max_wip_blocked_rate_increase_ratio": max(float(item["wip_blocked_rate_increase_ratio"]) for item in samples),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "input_dir": str(input_dir),
            "sample_interval_minutes": int(args.sample_interval_minutes),
            "rollback_sustained_minutes": int(args.rollback_sustained_minutes),
            "rollback_breach_streak": rollback_breach_streak,
        },
        "samples": samples,
        "summary": summary,
        "recommendation": recommendation,
    }

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Goal admission canary summary")
    print(f"- Sample count: {summary['sample_count']}")
    print(f"- Max queue rising streak: {summary['max_queue_rising_streak']}")
    print(f"- Recommendation: {recommendation['status']}")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
