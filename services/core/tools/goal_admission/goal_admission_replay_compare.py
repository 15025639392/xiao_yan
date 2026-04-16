#!/usr/bin/env python3
"""Compare baseline and candidate admission thresholds via deterministic replay."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path


REPO_CORE = Path(__file__).resolve().parents[2]
if str(REPO_CORE) not in sys.path:
    sys.path.insert(0, str(REPO_CORE))

from app.goals.admission import GoalAdmissionStore  # noqa: E402
from tools.goal_admission.goal_admission_phase3_driver import DriverConfig, Phase3Driver  # noqa: E402


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_threshold_order(config: DriverConfig) -> None:
    if config.defer_score > config.min_score:
        raise ValueError("defer_score must be <= min_score")
    if config.world_defer_score > config.world_min_score:
        raise ValueError("world_defer_score must be <= world_min_score")
    if config.chain_defer_score > config.chain_min_score:
        raise ValueError("chain_defer_score must be <= chain_min_score")


def _build_baseline_config(args: argparse.Namespace) -> DriverConfig:
    config = DriverConfig(
        iterations=max(1, int(args.iterations)),
        mode=args.mode,
        wip_limit=max(1, int(args.wip_limit)),
        min_score=_clamp_score(args.min_score),
        defer_score=_clamp_score(args.defer_score),
        world_min_score=_clamp_score(args.world_min_score),
        world_defer_score=_clamp_score(args.world_defer_score),
        chain_min_score=_clamp_score(args.chain_min_score),
        chain_defer_score=_clamp_score(args.chain_defer_score),
        sample_target=max(1, int(args.sample_target)),
        drop_target=max(0, int(args.drop_target)),
        defer_target=max(0, int(args.defer_target)),
        max_queue_size=max(0, int(args.max_queue_size)),
        world_enabled=bool(args.world_enabled),
        seed=int(args.seed),
    )
    _validate_threshold_order(config)
    return config


def _build_candidate_config(args: argparse.Namespace, baseline: DriverConfig) -> DriverConfig:
    changed = False
    candidate = replace(baseline)

    if args.candidate_wip_limit is not None:
        candidate.wip_limit = max(1, int(args.candidate_wip_limit))
        changed = True
    if args.candidate_min_score is not None:
        candidate.min_score = _clamp_score(args.candidate_min_score)
        changed = True
    if args.candidate_defer_score is not None:
        candidate.defer_score = _clamp_score(args.candidate_defer_score)
        changed = True
    if args.candidate_world_min_score is not None:
        candidate.world_min_score = _clamp_score(args.candidate_world_min_score)
        changed = True
    if args.candidate_world_defer_score is not None:
        candidate.world_defer_score = _clamp_score(args.candidate_world_defer_score)
        changed = True
    if args.candidate_chain_min_score is not None:
        candidate.chain_min_score = _clamp_score(args.candidate_chain_min_score)
        changed = True
    if args.candidate_chain_defer_score is not None:
        candidate.chain_defer_score = _clamp_score(args.candidate_chain_defer_score)
        changed = True
    if args.candidate_world_enabled is not None:
        candidate.world_enabled = bool(args.candidate_world_enabled)
        changed = True

    if not changed:
        raise ValueError("at least one candidate override is required")

    _validate_threshold_order(candidate)
    return candidate


def _run_profile(config: DriverConfig) -> dict:
    driver = Phase3Driver(config, GoalAdmissionStore.in_memory())
    return driver.run()


def _build_recommendation(baseline: dict, candidate: dict, delta_today: dict[str, int], delta_queue_size: int) -> dict:
    if candidate["phase3_ready"] and not baseline["phase3_ready"]:
        return {"status": "promote_candidate", "reason": "candidate reaches readiness while baseline does not"}
    if candidate["phase3_ready"] and baseline["phase3_ready"]:
        if delta_today["drop"] >= 0 and delta_queue_size <= 0:
            return {"status": "prefer_candidate", "reason": "both ready, candidate has non-worse noise suppression"}
        return {"status": "review", "reason": "both ready but trade-offs need manual review"}
    return {"status": "keep_baseline", "reason": "candidate readiness or queue behavior is weaker"}


def compare_profiles(baseline: dict, candidate: dict) -> dict:
    base_today = baseline["stats"]["today"]
    cand_today = candidate["stats"]["today"]
    keys = ("admit", "defer", "drop", "wip_blocked")
    delta_today = {key: int(cand_today[key]) - int(base_today[key]) for key in keys}
    delta_queue_size = int(candidate["stats"]["deferred_queue_size"]) - int(baseline["stats"]["deferred_queue_size"])
    recommendation = _build_recommendation(baseline, candidate, delta_today, delta_queue_size)
    return {
        "delta_today": delta_today,
        "delta_deferred_queue_size": delta_queue_size,
        "baseline_phase3_ready": bool(baseline["phase3_ready"]),
        "candidate_phase3_ready": bool(candidate["phase3_ready"]),
        "recommendation": recommendation,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate goal-admission settings.")
    parser.add_argument("--iterations", type=int, default=700)
    parser.add_argument("--seed", type=int, default=20260408)
    parser.add_argument("--mode", choices=["off", "shadow", "enforce"], default="enforce")
    parser.add_argument("--wip-limit", type=int, default=2)
    parser.add_argument("--min-score", type=float, default=0.68)
    parser.add_argument("--defer-score", type=float, default=0.45)
    parser.add_argument("--world-min-score", type=float, default=0.75)
    parser.add_argument("--world-defer-score", type=float, default=0.52)
    parser.add_argument("--chain-min-score", type=float, default=0.62)
    parser.add_argument("--chain-defer-score", type=float, default=0.45)
    parser.add_argument("--sample-target", type=int, default=500)
    parser.add_argument("--drop-target", type=int, default=80)
    parser.add_argument("--defer-target", type=int, default=80)
    parser.add_argument("--max-queue-size", type=int, default=120)
    parser.add_argument("--world-enabled", dest="world_enabled", action="store_true", default=True)
    parser.add_argument("--no-world-enabled", dest="world_enabled", action="store_false")

    parser.add_argument("--candidate-wip-limit", type=int, default=None)
    parser.add_argument("--candidate-min-score", type=float, default=None)
    parser.add_argument("--candidate-defer-score", type=float, default=None)
    parser.add_argument("--candidate-world-min-score", type=float, default=None)
    parser.add_argument("--candidate-world-defer-score", type=float, default=None)
    parser.add_argument("--candidate-chain-min-score", type=float, default=None)
    parser.add_argument("--candidate-chain-defer-score", type=float, default=None)
    parser.add_argument("--candidate-world-enabled", dest="candidate_world_enabled", action="store_true")
    parser.add_argument("--candidate-no-world-enabled", dest="candidate_world_enabled", action="store_false")
    parser.set_defaults(candidate_world_enabled=None)

    parser.add_argument("--output", type=str, default="", help="Optional path to write comparison report JSON.")
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        baseline_config = _build_baseline_config(args)
        candidate_config = _build_candidate_config(args, baseline_config)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    baseline_report = _run_profile(baseline_config)
    candidate_report = _run_profile(candidate_config)
    comparison = compare_profiles(baseline_report, candidate_report)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline_report,
        "candidate": candidate_report,
        "comparison": comparison,
    }

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Goal admission replay comparison")
    print(f"- Baseline ready: {'YES' if baseline_report['phase3_ready'] else 'NO'}")
    print(f"- Candidate ready: {'YES' if candidate_report['phase3_ready'] else 'NO'}")
    print(f"- Delta today: {comparison['delta_today']}")
    print(f"- Delta deferred queue size: {comparison['delta_deferred_queue_size']}")
    print(f"- Recommendation: {comparison['recommendation']['status']}")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
