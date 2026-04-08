#!/usr/bin/env python3
"""Render a release decision markdown from replay and canary summary reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _final_decision(replay_status: str, canary_status: str) -> tuple[str, str]:
    if canary_status == "rollback":
        return "建议回滚", "canary 已触发回滚条件，先止血再复盘"
    if replay_status in {"promote_candidate", "prefer_candidate"} and canary_status == "promote":
        return "可以放量", "回放与 canary 均支持放量"
    if canary_status == "hold":
        return "继续观察", "canary 暂未满足放量或回滚条件"
    return "继续观察", "需要人工复核回放与 canary 的组合结论"


def _build_markdown(
    *,
    replay: dict,
    canary: dict,
    replay_path: Path,
    canary_path: Path,
    owner_engineering: str,
    owner_product: str,
    owner_oncall: str,
) -> str:
    replay_status = str(replay.get("comparison", {}).get("recommendation", {}).get("status", "unknown"))
    replay_reason = str(replay.get("comparison", {}).get("recommendation", {}).get("reason", ""))
    canary_status = str(canary.get("recommendation", {}).get("status", "unknown"))
    canary_reason = str(canary.get("recommendation", {}).get("reason", ""))
    canary_triggers = canary.get("recommendation", {}).get("triggered_by", [])
    if not isinstance(canary_triggers, list):
        canary_triggers = []

    baseline_config = replay.get("baseline", {}).get("config", {})
    candidate_config = replay.get("candidate", {}).get("config", {})
    delta_today = replay.get("comparison", {}).get("delta_today", {})
    delta_queue = replay.get("comparison", {}).get("delta_deferred_queue_size", 0)
    canary_summary = canary.get("summary", {})

    final_status, final_reason = _final_decision(replay_status, canary_status)

    return f"""# Goal Admission Phase 3 发布报告

生成时间（UTC）：{datetime.now(timezone.utc).isoformat()}

## 1. 责任人与输入

- Engineering owner: {owner_engineering}
- Product owner: {owner_product}
- Oncall owner: {owner_oncall}
- Replay 报告：`{replay_path}`
- Canary 报告：`{canary_path}`

## 2. 参数对比（Baseline vs Candidate）

| 参数 | Baseline | Candidate |
|---|---:|---:|
| user_topic min/defer | {baseline_config.get("min_score", "-")} / {baseline_config.get("defer_score", "-")} | {candidate_config.get("min_score", "-")} / {candidate_config.get("defer_score", "-")} |
| world_event min/defer | {baseline_config.get("world_min_score", "-")} / {baseline_config.get("world_defer_score", "-")} | {candidate_config.get("world_min_score", "-")} / {candidate_config.get("world_defer_score", "-")} |
| chain_next min/defer | {baseline_config.get("chain_min_score", "-")} / {baseline_config.get("chain_defer_score", "-")} | {candidate_config.get("chain_min_score", "-")} / {candidate_config.get("chain_defer_score", "-")} |

## 3. 回放结论

- replay recommendation: `{replay_status}`
- replay reason: {replay_reason}
- delta today: `{delta_today}`
- delta deferred queue size: `{delta_queue}`

## 4. Canary 结论

- canary recommendation: `{canary_status}`
- canary reason: {canary_reason}
- triggered_by: `{canary_triggers}`
- sample_count: `{canary_summary.get("sample_count", "-")}`
- max_queue_rising_streak: `{canary_summary.get("max_queue_rising_streak", "-")}`
- max_drop_rate_increase_ratio: `{_format_percent(float(canary_summary.get("max_drop_rate_increase_ratio", 0.0)))}`
- max_wip_blocked_rate_increase_ratio: `{_format_percent(float(canary_summary.get("max_wip_blocked_rate_increase_ratio", 0.0)))}`

## 5. 最终建议

- 最终建议：{final_status}
- 判定理由：{final_reason}

## 6. 签署

- Engineering owner：`[ ] 同意  [ ] 反对`
- Product owner：`[ ] 同意  [ ] 反对`
- Oncall owner：`[ ] 同意  [ ] 反对`
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate markdown release report from replay/canary JSON.")
    parser.add_argument("--replay-report", type=str, required=True)
    parser.add_argument("--canary-summary", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--owner-engineering", type=str, default="TBD")
    parser.add_argument("--owner-product", type=str, default="TBD")
    parser.add_argument("--owner-oncall", type=str, default="TBD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    replay_path = Path(args.replay_report).expanduser()
    canary_path = Path(args.canary_summary).expanduser()
    output_path = Path(args.output).expanduser()

    try:
        replay = _load_json(replay_path)
        canary = _load_json(canary_path)
    except FileNotFoundError as error:
        print(str(error))
        return 2

    content = _build_markdown(
        replay=replay,
        canary=canary,
        replay_path=replay_path,
        canary_path=canary_path,
        owner_engineering=args.owner_engineering,
        owner_product=args.owner_product,
        owner_oncall=args.owner_oncall,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"release report generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
