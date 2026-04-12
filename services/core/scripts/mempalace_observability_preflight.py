#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.llm.schemas import ChatMessage
from app.main import app, get_chat_gateway, get_mempalace_adapter


class _StubGateway:
    def create_response(self, messages, instructions=None):
        user_text = str(messages[-1].content)
        return {
            "response_id": "resp_preflight",
            "output_text": f"preflight:{user_text}",
        }

    def stream_response(self, messages, instructions=None):
        user_text = str(messages[-1].content)
        yield {"type": "response_started", "response_id": "resp_preflight"}
        yield {"type": "text_delta", "delta": "preflight:"}
        yield {"type": "text_delta", "delta": user_text}
        yield {
            "type": "response_completed",
            "response_id": "resp_preflight",
            "output_text": f"preflight:{user_text}",
        }

    def close(self):
        return None


class _StubMemPalaceAdapter:
    def __init__(self) -> None:
        self._history: list[dict[str, str | None]] = []

    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        _ = exclude_current_room
        _ = retrieval_weight
        if not query.strip():
            return ""
        lines = [
            "【长期记忆检索】",
            "- wing_xiaoyan/knowledge (相似度 0.88) 你喜欢结构化输出。",
            "- wing_xiaoyan/autobio (相似度 0.81) 你最近在推进知识库建设。",
        ]
        safe_hits = max_hits if isinstance(max_hits, int) and max_hits > 0 else len(lines) - 1
        return "\n".join([lines[0], *lines[1 : 1 + safe_hits]])

    def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
        _ = limit
        messages = [ChatMessage(role=item["role"], content=item["content"]) for item in self._history[-6:]]
        messages.append(ChatMessage(role="user", content=user_message))
        return messages

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0):
        _ = offset
        if limit <= 0:
            return []
        return list(reversed(self._history[-limit:]))

    def record_exchange(self, user_message: str, assistant_response: str, assistant_session_id: str | None = None) -> bool:
        self._history.append(
            {
                "id": f"pf_user_{len(self._history)}",
                "role": "user",
                "content": user_message,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "session_id": None,
            }
        )
        self._history.append(
            {
                "id": f"pf_assistant_{len(self._history)}",
                "role": "assistant",
                "content": assistant_response,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "session_id": assistant_session_id,
            }
        )
        return True


def _default_output_path(repo_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "docs" / "runbooks" / "evidence" / f"mempalace-preflight-{timestamp}.json"


def _build_prompts(turns: int) -> list[str]:
    base_prompts = [
        "我们继续推进知识库建设，先给我一个结构化小结。",
        "回顾一下刚才的重点，按结论和风险分开。",
        "如果我要继续推进，请给我唯一下一步。",
        "你还记得我偏好简洁结论吗？",
        "把关键行动项列成 3 条。",
        "再给一次来源可追溯的回答。",
        "这轮里有哪些长期记忆被命中了？",
        "请保持结构化输出并继续。",
        "总结今天我们在知识库任务上的进展。",
        "补一条风险提醒，别太长。",
        "如果继续开发，优先做什么？",
        "最后再给一次可执行下一步。",
    ]
    if turns <= len(base_prompts):
        return base_prompts[:turns]
    prompts = list(base_prompts)
    for index in range(len(base_prompts), turns):
        prompts.append(f"第 {index + 1} 轮：继续按结构化方式总结。")
    return prompts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MemPalace observability preflight via TestClient.")
    parser.add_argument("--turns", type=int, default=12, help="Number of chat turns, minimum 10.")
    parser.add_argument("--output", type=str, default="", help="Report output path (json).")
    args = parser.parse_args()

    turns = max(10, int(args.turns))
    repo_root = Path(__file__).resolve().parents[3]
    output_path = Path(args.output).expanduser().resolve() if args.output else _default_output_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gateway = _StubGateway()
    mempalace_adapter = _StubMemPalaceAdapter()
    app.dependency_overrides[get_chat_gateway] = lambda: gateway
    app.dependency_overrides[get_mempalace_adapter] = lambda: mempalace_adapter

    prompts = _build_prompts(turns)
    results: list[dict[str, object]] = []
    observability_snapshot: dict = {}

    try:
        with TestClient(app) as client:
            for index, prompt in enumerate(prompts):
                response = client.post("/chat", json={"message": prompt})
                body = response.json()
                results.append(
                    {
                        "turn": index + 1,
                        "status_code": response.status_code,
                        "assistant_message_id": body.get("assistant_message_id") if isinstance(body, dict) else None,
                    }
                )
            observability_response = client.get("/memory/observability")
            observability_snapshot = observability_response.json()
    finally:
        app.dependency_overrides.clear()

    success_count = sum(1 for item in results if item["status_code"] == 200)
    failed_count = len(results) - success_count
    alerts = observability_snapshot.get("alerts") if isinstance(observability_snapshot, dict) else []

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local-preflight-simulation",
        "turns": turns,
        "chat_results": results,
        "summary": {
            "success_count": success_count,
            "failed_count": failed_count,
            "alerts": alerts,
            "pass": failed_count == 0 and isinstance(alerts, list) and len(alerts) == 0,
        },
        "observability": observability_snapshot,
        "notes": [
            "This preflight uses local TestClient with stub gateway/mempalace adapter.",
            "Use real service traffic for final grey-release validation.",
        ],
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[preflight] turns={turns} success={success_count} failed={failed_count}")
    print(f"[preflight] report={output_path}")
    if isinstance(alerts, list) and alerts:
        print(f"[preflight] alerts={','.join(alerts)}")
    else:
        print("[preflight] alerts=none")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
