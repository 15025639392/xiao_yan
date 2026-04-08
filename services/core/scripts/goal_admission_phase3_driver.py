#!/usr/bin/env python3
"""Drive synthetic admission samples and evaluate Phase 3 readiness.

Usage examples:

  # In-memory run (safe default), prints summary
  python services/core/scripts/goal_admission_phase3_driver.py --iterations 700

  # Persist to default admission store (will affect live stats file)
  python services/core/scripts/goal_admission_phase3_driver.py --persist default

  # Export JSON report
  python services/core/scripts/goal_admission_phase3_driver.py --output /tmp/phase3-report.json --print-json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_CORE = Path(__file__).resolve().parents[1]
if str(REPO_CORE) not in sys.path:
    sys.path.insert(0, str(REPO_CORE))

from app.config import get_goal_admission_storage_path  # noqa: E402
from app.goals.admission import (  # noqa: E402
    AdmissionDecision,
    GoalAdmissionService,
    GoalAdmissionStore,
    GoalCandidate,
    GoalCandidateSource,
)
from app.goals.models import Goal, GoalStatus  # noqa: E402
from app.goals.repository import InMemoryGoalRepository  # noqa: E402
from app.memory.models import MemoryEvent  # noqa: E402


@dataclass
class DriverConfig:
    iterations: int
    mode: str
    wip_limit: int
    min_score: float
    defer_score: float
    world_min_score: float
    world_defer_score: float
    chain_min_score: float
    chain_defer_score: float
    sample_target: int
    drop_target: int
    defer_target: int
    max_queue_size: int
    world_enabled: bool
    seed: int


class Phase3Driver:
    def __init__(self, config: DriverConfig, store: GoalAdmissionStore) -> None:
        self.config = config
        self.goal_repository = InMemoryGoalRepository()
        self.admission_service = GoalAdmissionService(
            store=store,
            mode=config.mode,  # type: ignore[arg-type]
            min_score=config.min_score,
            defer_score=config.defer_score,
            world_min_score=config.world_min_score,
            world_defer_score=config.world_defer_score,
            chain_min_score=config.chain_min_score,
            chain_defer_score=config.chain_defer_score,
            wip_limit=config.wip_limit,
            world_enabled=config.world_enabled,
        )
        self.now = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)
        self.recent_events: list[MemoryEvent] = []
        self.last_noise_content = "嗯"
        self.rng = random.Random(config.seed)

    def run(self) -> dict:
        for index in range(self.config.iterations):
            self._run_iteration(index)
            self.now += timedelta(seconds=61)
            self._try_promote_deferred()

        stats = self.admission_service.get_stats(self.now)
        today = stats["today"]
        total = int(today["admit"]) + int(today["defer"]) + int(today["drop"])
        ready = (
            total >= self.config.sample_target
            and int(today["drop"]) >= self.config.drop_target
            and int(today["defer"]) >= self.config.defer_target
            and int(stats["deferred_queue_size"]) <= self.config.max_queue_size
        )

        return {
            "timestamp": self.now.isoformat(),
            "config": {
                "iterations": self.config.iterations,
                "mode": self.config.mode,
                "wip_limit": self.config.wip_limit,
                "min_score": self.config.min_score,
                "defer_score": self.config.defer_score,
                "world_min_score": self.config.world_min_score,
                "world_defer_score": self.config.world_defer_score,
                "chain_min_score": self.config.chain_min_score,
                "chain_defer_score": self.config.chain_defer_score,
                "sample_target": self.config.sample_target,
                "drop_target": self.config.drop_target,
                "defer_target": self.config.defer_target,
                "max_queue_size": self.config.max_queue_size,
                "seed": self.config.seed,
            },
            "stats": stats,
            "evidence": {
                "total_decisions": total,
                "drop_count": int(today["drop"]),
                "defer_count": int(today["defer"]),
                "queue_size": int(stats["deferred_queue_size"]),
            },
            "phase3_ready": ready,
        }

    def _run_iteration(self, index: int) -> None:
        scenario = index % 10
        if scenario == 0:
            self._run_low_user_noise_new_drop(index)
            return
        if scenario == 1:
            self._run_low_user_noise_duplicate_defer()
            return
        if scenario in {2, 3}:
            self._run_high_user_actionable()
            return
        if scenario in {4, 5}:
            self._run_world_event()
            return
        if scenario == 6:
            self._run_chain_candidate(generation=2)
            return
        if scenario == 7:
            self._run_chain_candidate(generation=12)
            return
        if scenario == 9:
            self._run_low_user_noise_new_drop(index + 10000)
            return
        self._run_wip_pressure()

    def _run_low_user_noise_new_drop(self, index: int) -> None:
        # Deliberately keep persistence low by using unrelated recent event content.
        content = f"噪声词{index}"
        self.last_noise_content = content
        self._append_event("chat", "随便聊聊", role="user")
        candidate = GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title=f"持续理解用户最近在意的话题：{content}",
            source_content=content,
        )
        self._evaluate(candidate)

    def _run_low_user_noise_duplicate_defer(self) -> None:
        # Repeat last low-quality candidate quickly to trigger duplicate defer.
        content = self.last_noise_content
        self._append_event("chat", "随便聊聊", role="user")
        candidate = GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title=f"持续理解用户最近在意的话题：{content}",
            source_content=content,
        )
        self._evaluate(candidate)

    def _run_high_user_actionable(self) -> None:
        content = self.rng.choice(
            [
                "看看现在在哪个目录",
                "看看现在几点",
                "检查一下当前文件目录",
                "确认现在是什么时间",
            ]
        )
        self._append_event("chat", content, role="user")
        # Add persistence signal occasionally.
        if self.rng.random() > 0.4:
            self._append_event("chat", content, role="user")
        candidate = GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title=f"持续理解用户最近在意的话题：{content}",
            source_content=content,
        )
        self._evaluate(candidate, auto_complete=True)

    def _run_world_event(self) -> None:
        content = self.rng.choice(
            [
                "清晨很安静，我还惦记着整理今天的对话记忆。",
                "夜里有点困，正在回看今天推进到哪一步。",
                "刚刚状态波动，短时间不适合继续展开。",
            ]
        )
        self._append_event("world", content)
        candidate = GoalCandidate(
            source_type=GoalCandidateSource.WORLD_EVENT,
            title=f"继续消化自己刚经历的状态：{content[:24]}",
            source_content=content,
            chain_id=f"world-{index_hash(content)}",
        )
        self._evaluate(candidate, auto_complete=True)

    def _run_chain_candidate(self, generation: int) -> None:
        content = "清晨很安静，我还惦记着整理今天的对话记忆。"
        self._append_event("world", content)
        candidate = GoalCandidate(
            source_type=GoalCandidateSource.CHAIN_NEXT,
            title="继续推进：继续消化自己刚经历的状态：整理今天的对话",
            source_content=content,
            chain_id="chain-demo",
            parent_goal_id="goal-parent-demo",
            generation=generation,
        )
        self._evaluate(candidate, auto_complete=True)

    def _run_wip_pressure(self) -> None:
        self.goal_repository = InMemoryGoalRepository()
        self.goal_repository.save_goal(Goal(title="看看现在在哪个目录", status=GoalStatus.ACTIVE))
        self.goal_repository.save_goal(Goal(title="整理今天的对话记忆", status=GoalStatus.ACTIVE))
        content = "看看文件目录"
        self._append_event("chat", content, role="user")
        candidate = GoalCandidate(
            source_type=GoalCandidateSource.USER_TOPIC,
            title=f"持续理解用户最近在意的话题：{content}",
            source_content=content,
        )
        self._evaluate(candidate)
        # Reset active goals so later iterations can still create admits.
        self.goal_repository = InMemoryGoalRepository()

    def _evaluate(self, candidate: GoalCandidate, *, auto_complete: bool = False) -> None:
        result = self.admission_service.evaluate_candidate(
            candidate,
            now=self.now,
            active_goals=self.goal_repository.list_active_goals(),
            all_goals=self.goal_repository.list_goals(),
            recent_events=list(self.recent_events[-20:]),
        )
        if result.applied_decision != AdmissionDecision.ADMIT:
            return

        goal = self.goal_repository.save_goal(
            Goal(
                title=candidate.title,
                source=candidate.source_content,
                chain_id=candidate.chain_id,
                parent_goal_id=candidate.parent_goal_id,
                generation=candidate.generation,
            )
        )
        if auto_complete:
            self.goal_repository.update_status(goal.id, GoalStatus.COMPLETED)

    def _try_promote_deferred(self) -> None:
        deferred = self.admission_service.pop_due_candidate(self.now)
        if deferred is None:
            return
        self._evaluate(deferred, auto_complete=True)

    def _append_event(self, kind: str, content: str, role: str | None = None) -> None:
        self.recent_events.append(
            MemoryEvent(
                kind=kind,
                content=content,
                role=role,
                created_at=self.now,
            )
        )
        if len(self.recent_events) > 60:
            self.recent_events = self.recent_events[-60:]


def index_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drive admission samples for Phase 3 readiness checks.")
    parser.add_argument("--iterations", type=int, default=700, help="How many synthetic iterations to run.")
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
    parser.add_argument("--seed", type=int, default=20260408)
    parser.add_argument("--world-enabled", dest="world_enabled", action="store_true", default=True)
    parser.add_argument("--no-world-enabled", dest="world_enabled", action="store_false")
    parser.add_argument(
        "--persist",
        choices=["none", "default", "path"],
        default="none",
        help="Persist stats queue to default store or a custom --store-path.",
    )
    parser.add_argument("--store-path", type=str, default="", help="Custom store path when --persist=path.")
    parser.add_argument("--output", type=str, default="", help="Optional path to write JSON report.")
    parser.add_argument("--print-json", action="store_true", help="Print full report JSON.")
    return parser.parse_args()


def build_store(args: argparse.Namespace) -> GoalAdmissionStore:
    if args.persist == "none":
        return GoalAdmissionStore.in_memory()
    if args.persist == "default":
        return GoalAdmissionStore(get_goal_admission_storage_path())
    if not args.store_path:
        raise ValueError("--store-path is required when --persist=path")
    return GoalAdmissionStore(Path(args.store_path).expanduser())


def main() -> int:
    args = parse_args()
    min_score = max(0.0, min(1.0, args.min_score))
    defer_score = max(0.0, min(1.0, args.defer_score))
    world_min_score = max(0.0, min(1.0, args.world_min_score))
    world_defer_score = max(0.0, min(1.0, args.world_defer_score))
    chain_min_score = max(0.0, min(1.0, args.chain_min_score))
    chain_defer_score = max(0.0, min(1.0, args.chain_defer_score))

    if defer_score > min_score:
        raise ValueError("--defer-score must be <= --min-score")
    if world_defer_score > world_min_score:
        raise ValueError("--world-defer-score must be <= --world-min-score")
    if chain_defer_score > chain_min_score:
        raise ValueError("--chain-defer-score must be <= --chain-min-score")

    config = DriverConfig(
        iterations=args.iterations,
        mode=args.mode,
        wip_limit=max(1, args.wip_limit),
        min_score=min_score,
        defer_score=defer_score,
        world_min_score=world_min_score,
        world_defer_score=world_defer_score,
        chain_min_score=chain_min_score,
        chain_defer_score=chain_defer_score,
        sample_target=max(1, args.sample_target),
        drop_target=max(0, args.drop_target),
        defer_target=max(0, args.defer_target),
        max_queue_size=max(0, args.max_queue_size),
        world_enabled=bool(args.world_enabled),
        seed=int(args.seed),
    )
    store = build_store(args)
    driver = Phase3Driver(config, store)
    report = driver.run()

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    evidence = report["evidence"]
    print("Phase 3 readiness evidence")
    print(f"- Total decisions: {evidence['total_decisions']}")
    print(f"- Drop count: {evidence['drop_count']}")
    print(f"- Defer count: {evidence['defer_count']}")
    print(f"- Deferred queue size: {evidence['queue_size']}")
    print(f"- Ready: {'YES' if report['phase3_ready'] else 'NO'}")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
