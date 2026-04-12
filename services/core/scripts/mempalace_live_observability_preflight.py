#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


def _default_output_path(repo_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "docs" / "runbooks" / "evidence" / f"mempalace-live-preflight-{timestamp}.json"


def _build_prompts(turns: int) -> list[str]:
    base_prompts = [
        "请用一句话回答：我们继续知识库建设。",
        "请一句话回顾上条重点。",
        "请给唯一下一步。",
        "请一句话回答：继续推进。",
        "请列 2 条行动项。",
        "请一句话提示一个风险。",
        "请一句话回答：保持结构化。",
        "请一句话总结当前进展。",
        "请给 1 条可执行动作。",
        "请一句话回答：继续。",
        "请一句话回答：记住我们的目标是知识库建设。",
        "请一句话给收尾建议。",
    ]
    if turns <= len(base_prompts):
        return base_prompts[:turns]
    prompts = list(base_prompts)
    for index in range(len(base_prompts), turns):
        prompts.append(f"第 {index + 1} 轮：请一句话继续知识库建设进展。")
    return prompts


def _safe_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * percentile
    lower = int(math.floor(rank))
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    return round(value, 3)


def _safe_json_response(client: httpx.Client, path: str) -> dict[str, Any]:
    try:
        response = client.get(path)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw": payload}
    except Exception as exc:  # pragma: no cover - best effort diagnostics
        return {"error": repr(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run MemPalace live observability preflight via HTTP /chat calls."
    )
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8000", help="Service base URL.")
    parser.add_argument("--turns", type=int, default=12, help="Number of chat turns (recommended 10~20).")
    parser.add_argument("--retries", type=int, default=2, help="Retries per failed turn (default 2).")
    parser.add_argument("--connect-timeout", type=float, default=5.0, help="HTTP connect timeout in seconds.")
    parser.add_argument("--read-timeout", type=float, default=45.0, help="HTTP read timeout in seconds.")
    parser.add_argument("--write-timeout", type=float, default=10.0, help="HTTP write timeout in seconds.")
    parser.add_argument("--pool-timeout", type=float, default=10.0, help="HTTP pool timeout in seconds.")
    parser.add_argument("--backoff-base", type=float, default=1.5, help="Retry backoff base in seconds.")
    parser.add_argument("--sleep-ms", type=int, default=0, help="Optional delay between turns in milliseconds.")
    parser.add_argument("--output", type=str, default="", help="Report output path (json).")
    parser.add_argument(
        "--reset-first",
        action="store_true",
        help="Reset /memory/observability window before running live traffic.",
    )
    parser.add_argument(
        "--strict-alerts",
        action="store_true",
        help="Exit non-zero when observability snapshot contains alerts.",
    )
    args = parser.parse_args()

    turns = max(1, int(args.turns))
    retries = max(0, int(args.retries))
    repo_root = Path(__file__).resolve().parents[3]
    output_path = Path(args.output).expanduser().resolve() if args.output else _default_output_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompts = _build_prompts(turns)

    timeout = httpx.Timeout(
        connect=max(0.1, float(args.connect_timeout)),
        read=max(0.1, float(args.read_timeout)),
        write=max(0.1, float(args.write_timeout)),
        pool=max(0.1, float(args.pool_timeout)),
    )

    run_started_at = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    observability_before: dict[str, Any]
    observability_after: dict[str, Any]

    with httpx.Client(base_url=args.base_url, timeout=timeout) as client:
        reset_result: dict[str, Any] | None = None
        if args.reset_first:
            try:
                reset_response = client.post("/memory/observability/reset")
                reset_response.raise_for_status()
                reset_payload = reset_response.json()
                reset_result = reset_payload if isinstance(reset_payload, dict) else {"raw": reset_payload}
            except Exception as exc:  # noqa: BLE001
                reset_result = {"error": repr(exc)}

        observability_before = _safe_json_response(client, "/memory/observability")

        for index, prompt in enumerate(prompts, start=1):
            turn_started = time.perf_counter()
            attempt_logs: list[dict[str, Any]] = []
            final_status_code: int | None = None
            assistant_message_id: str | None = None
            final_error: str | None = None

            for attempt in range(1, retries + 2):
                attempt_started = time.perf_counter()
                try:
                    response = client.post("/chat", json={"message": prompt})
                    attempt_elapsed = round((time.perf_counter() - attempt_started) * 1000, 3)
                    final_status_code = response.status_code
                    body_text = response.text or ""
                    payload: dict[str, Any] | None = None
                    if response.headers.get("content-type", "").startswith("application/json"):
                        try:
                            raw_payload = response.json()
                            if isinstance(raw_payload, dict):
                                payload = raw_payload
                        except Exception:
                            payload = None
                    if isinstance(payload, dict):
                        assistant_message_id = payload.get("assistant_message_id")

                    attempt_logs.append(
                        {
                            "attempt": attempt,
                            "ok": response.status_code == 200,
                            "status_code": response.status_code,
                            "duration_ms": attempt_elapsed,
                            "error": None,
                            "assistant_message_id": assistant_message_id,
                            "body_snippet": body_text[:200],
                        }
                    )

                    if response.status_code == 200:
                        final_error = None
                        break
                    final_error = f"HTTP {response.status_code}"
                except Exception as exc:
                    attempt_elapsed = round((time.perf_counter() - attempt_started) * 1000, 3)
                    final_error = repr(exc)
                    attempt_logs.append(
                        {
                            "attempt": attempt,
                            "ok": False,
                            "status_code": None,
                            "duration_ms": attempt_elapsed,
                            "error": final_error,
                            "assistant_message_id": None,
                            "body_snippet": "",
                        }
                    )

                if attempt <= retries:
                    time.sleep(max(0.0, float(args.backoff_base)) * attempt)

            turn_elapsed = round((time.perf_counter() - turn_started) * 1000, 3)
            results.append(
                {
                    "turn": index,
                    "prompt": prompt,
                    "status_code": final_status_code,
                    "ok": final_status_code == 200,
                    "attempts": len(attempt_logs),
                    "elapsed_ms_total": turn_elapsed,
                    "assistant_message_id": assistant_message_id,
                    "error": final_error,
                    "attempt_logs": attempt_logs,
                }
            )

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)

        observability_after = _safe_json_response(client, "/memory/observability")

    success_count = sum(1 for item in results if item["ok"])
    failed_count = len(results) - success_count
    elapsed_values = [float(item["elapsed_ms_total"]) for item in results]
    alerts = observability_after.get("alerts") if isinstance(observability_after, dict) else None

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live-http-preflight",
        "base_url": args.base_url,
        "settings": {
            "turns": turns,
            "retries": retries,
            "timeout": {
                "connect_s": timeout.connect,
                "read_s": timeout.read,
                "write_s": timeout.write,
                "pool_s": timeout.pool,
            },
            "backoff_base_s": max(0.0, float(args.backoff_base)),
            "sleep_ms": max(0, int(args.sleep_ms)),
        },
        "chat_results": results,
        "summary": {
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": round(success_count / len(results), 4) if results else None,
            "client_elapsed_ms": {
                "avg": round(sum(elapsed_values) / len(elapsed_values), 3) if elapsed_values else None,
                "p50": _safe_percentile(elapsed_values, 0.5),
                "p95": _safe_percentile(elapsed_values, 0.95),
                "max": round(max(elapsed_values), 3) if elapsed_values else None,
            },
        },
        "observability_before": observability_before,
        "observability_after": observability_after,
        "observability_reset": reset_result,
        "notes": [
            "Live HTTP calls against local running service.",
            "Report is persisted even when partial failures/timeouts occur.",
        ],
        "run_window": {
            "started_at": run_started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[live-preflight] report={output_path}")
    print(f"[live-preflight] success={success_count}/{len(results)} failed={failed_count}")
    if isinstance(alerts, list) and alerts:
        print(f"[live-preflight] alerts={alerts}")
    else:
        print("[live-preflight] alerts=none")

    if failed_count > 0:
        return 1
    if args.strict_alerts and isinstance(alerts, list) and alerts:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
