#!/usr/bin/env python3
"""Generate mock goal-admission stats snapshots for canary rehearsal."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def _build_payload(*, admit: int, defer: int, drop: int, wip_blocked: int, queue: int) -> dict:
    return {
        "mode": "enforce",
        "today": {
            "admit": admit,
            "defer": defer,
            "drop": drop,
            "wip_blocked": wip_blocked,
        },
        "deferred_queue_size": queue,
        "thresholds": {
            "user_topic": {"min_score": 0.72, "defer_score": 0.50},
            "world_event": {"min_score": 0.78, "defer_score": 0.55},
            "chain_next": {"min_score": 0.66, "defer_score": 0.46},
        },
    }


def _generate_healthy_samples(count: int, rng: random.Random) -> list[dict]:
    samples: list[dict] = []
    admit = 20
    defer = 10
    drop = 4
    wip_blocked = 2
    queue = 6
    for _ in range(count):
        admit += rng.randint(2, 5)
        defer += rng.randint(1, 2)
        drop += rng.randint(0, 1)
        wip_blocked += rng.randint(0, 1)
        queue = max(1, queue + rng.choice([-1, 0]))
        samples.append(
            _build_payload(
                admit=admit,
                defer=defer,
                drop=drop,
                wip_blocked=wip_blocked,
                queue=queue,
            )
        )
    return samples


def _generate_queue_growth_samples(count: int, rng: random.Random) -> list[dict]:
    samples: list[dict] = []
    admit = 20
    defer = 10
    drop = 2
    wip_blocked = 1
    queue = 1
    for _ in range(count):
        admit += rng.randint(1, 3)
        defer += rng.randint(1, 3)
        drop += rng.randint(0, 1)
        wip_blocked += rng.randint(0, 1)
        queue += rng.randint(1, 2)
        samples.append(
            _build_payload(
                admit=admit,
                defer=defer,
                drop=drop,
                wip_blocked=wip_blocked,
                queue=queue,
            )
        )
    return samples


def _generate_drop_spike_samples(count: int, rng: random.Random) -> list[dict]:
    samples: list[dict] = []
    admit = 20
    defer = 10
    drop = 2
    wip_blocked = 1
    queue = 4
    spike_start = max(1, count // 2)
    for index in range(count):
        admit += rng.randint(1, 3)
        defer += rng.randint(1, 2)
        if index >= spike_start:
            drop += rng.randint(2, 4)
            wip_blocked += rng.randint(1, 2)
        else:
            drop += rng.randint(0, 1)
            wip_blocked += rng.randint(0, 1)
        queue = max(1, queue + rng.choice([-1, 0, 1]))
        samples.append(
            _build_payload(
                admit=admit,
                defer=defer,
                drop=drop,
                wip_blocked=wip_blocked,
                queue=queue,
            )
        )
    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mock canary stats samples.")
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument(
        "--scenario",
        choices=["healthy", "queue_growth", "drop_spike"],
        default="healthy",
    )
    parser.add_argument("--seed", type=int, default=20260408)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    count = int(args.count)
    if count <= 0:
        print("count must be > 0")
        return 2

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("stats-*.json"):
        existing.unlink()

    rng = random.Random(int(args.seed))
    if args.scenario == "healthy":
        samples = _generate_healthy_samples(count, rng)
    elif args.scenario == "queue_growth":
        samples = _generate_queue_growth_samples(count, rng)
    else:
        samples = _generate_drop_spike_samples(count, rng)

    for index, payload in enumerate(samples, start=1):
        target = output_dir / f"stats-{index:02d}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("mock samples generated")
    print(f"- scenario: {args.scenario}")
    print(f"- count: {count}")
    print(f"- output_dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
