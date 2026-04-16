#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


def _default_output_path(repo_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "docs" / "runbooks" / "evidence" / f"mempalace-gray-watch-{timestamp}.json"


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll /memory/observability for gray-release watching.")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8000", help="Service base URL.")
    parser.add_argument("--interval-seconds", type=int, default=300, help="Polling interval in seconds.")
    parser.add_argument("--iterations", type=int, default=0, help="Number of polls. 0 means duration-based mode.")
    parser.add_argument("--duration-minutes", type=int, default=0, help="Duration mode in minutes when iterations=0.")
    parser.add_argument("--required-latency-samples", type=int, default=20)
    parser.add_argument("--required-write-samples", type=int, default=20)
    parser.add_argument("--required-quality-samples", type=int, default=20)
    parser.add_argument(
        "--reset-first",
        action="store_true",
        help="Reset /memory/observability window before starting watch.",
    )
    parser.add_argument("--output", type=str, default="", help="Report output path (json).")
    args = parser.parse_args()

    if args.iterations <= 0 and args.duration_minutes <= 0:
        raise SystemExit("either --iterations > 0 or --duration-minutes > 0 is required")

    interval_seconds = max(1, int(args.interval_seconds))
    required_latency_samples = max(1, int(args.required_latency_samples))
    required_write_samples = max(1, int(args.required_write_samples))
    required_quality_samples = max(1, int(args.required_quality_samples))

    repo_root = Path(__file__).resolve().parents[4]
    output_path = Path(args.output).expanduser().resolve() if args.output else _default_output_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    planned_iterations = int(args.iterations)
    if planned_iterations <= 0:
        planned_iterations = max(1, int((args.duration_minutes * 60) / interval_seconds))

    snapshots: list[dict[str, Any]] = []
    request_errors: list[dict[str, str]] = []

    with httpx.Client(base_url=args.base_url, timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0)) as client:
        reset_result: dict[str, Any] | None = None
        if args.reset_first:
            try:
                reset_response = client.post("/memory/observability/reset")
                reset_response.raise_for_status()
                reset_payload = reset_response.json()
                reset_result = reset_payload if isinstance(reset_payload, dict) else {"raw": reset_payload}
            except Exception as exc:  # noqa: BLE001
                reset_result = {"error": repr(exc)}

        for index in range(planned_iterations):
            now = datetime.now(timezone.utc)
            sample: dict[str, Any] = {
                "sample_index": index + 1,
                "timestamp": now.isoformat(),
            }
            try:
                response = client.get("/memory/observability")
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    sample["payload"] = payload
                else:
                    sample["payload"] = {"raw": payload}
            except Exception as exc:  # noqa: BLE001
                sample["error"] = repr(exc)
                request_errors.append({"timestamp": now.isoformat(), "error": repr(exc)})
            snapshots.append(sample)
            if index < planned_iterations - 1:
                time.sleep(interval_seconds)

    alerts_union: set[str] = set()
    retrieval_counts: list[int] = []
    chat_counts: list[int] = []
    quality_queries: list[int] = []
    write_attempts: list[int] = []
    chat_p95_values: list[float] = []
    retrieval_p95_values: list[float] = []

    for item in snapshots:
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        alerts = payload.get("alerts")
        if isinstance(alerts, list):
            for alert in alerts:
                if isinstance(alert, str) and alert:
                    alerts_union.add(alert)

        retrieval_count = _safe_get(payload, "latency", "retrieval_ms", "count")
        chat_count = _safe_get(payload, "latency", "chat_ms", "count")
        query_count = _safe_get(payload, "quality", "queries")
        write_count = _safe_get(payload, "write", "attempts")
        retrieval_p95 = _to_float(_safe_get(payload, "latency", "retrieval_ms", "p95"))
        chat_p95 = _to_float(_safe_get(payload, "latency", "chat_ms", "p95"))

        retrieval_counts.append(int(retrieval_count or 0))
        chat_counts.append(int(chat_count or 0))
        quality_queries.append(int(query_count or 0))
        write_attempts.append(int(write_count or 0))
        if retrieval_p95 is not None:
            retrieval_p95_values.append(round(retrieval_p95, 3))
        if chat_p95 is not None:
            chat_p95_values.append(round(chat_p95, 3))

    latest_payload: dict[str, Any] | None = None
    for item in reversed(snapshots):
        payload = item.get("payload")
        if isinstance(payload, dict):
            latest_payload = payload
            break

    latest_retrieval_count = retrieval_counts[-1] if retrieval_counts else 0
    latest_chat_count = chat_counts[-1] if chat_counts else 0
    latest_quality_queries = quality_queries[-1] if quality_queries else 0
    latest_write_attempts = write_attempts[-1] if write_attempts else 0
    data_sufficiency = {
        "latency": latest_retrieval_count >= required_latency_samples and latest_chat_count >= required_latency_samples,
        "quality": latest_quality_queries >= required_quality_samples,
        "write": latest_write_attempts >= required_write_samples,
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "gray-observability-watch",
        "base_url": args.base_url,
        "settings": {
            "interval_seconds": interval_seconds,
            "planned_iterations": planned_iterations,
            "required_latency_samples": required_latency_samples,
            "required_write_samples": required_write_samples,
            "required_quality_samples": required_quality_samples,
        },
        "samples": snapshots,
        "summary": {
            "total_samples": len(snapshots),
            "request_error_count": len(request_errors),
            "alerts_union": sorted(alerts_union),
            "latest_counts": {
                "retrieval": latest_retrieval_count,
                "chat": latest_chat_count,
                "quality_queries": latest_quality_queries,
                "write_attempts": latest_write_attempts,
            },
            "max_p95": {
                "retrieval_ms": max(retrieval_p95_values) if retrieval_p95_values else None,
                "chat_ms": max(chat_p95_values) if chat_p95_values else None,
            },
            "data_sufficiency": data_sufficiency,
            "gate_pass_no_alerts": len(alerts_union) == 0,
        },
        "latest_observability": latest_payload,
        "observability_reset": reset_result,
        "request_errors": request_errors,
        "notes": [
            "This watch script only polls observability snapshots and does not inject traffic.",
            "If traffic is low, data_sufficiency may remain false even when alerts are empty.",
        ],
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[gray-watch] report={output_path}")
    print(f"[gray-watch] samples={len(snapshots)} request_errors={len(request_errors)}")
    print(f"[gray-watch] alerts_union={sorted(alerts_union)}")
    print(f"[gray-watch] data_sufficiency={data_sufficiency}")

    return 0 if len(request_errors) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
