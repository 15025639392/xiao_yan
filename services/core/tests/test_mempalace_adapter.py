from app.memory.mempalace_adapter import MemPalaceAdapter


def test_mempalace_adapter_returns_empty_for_blank_query():
    adapter = MemPalaceAdapter()
    assert adapter.search_context("   ") == ""


def test_mempalace_adapter_formats_search_results_into_prompt_context():
    def _stub_search(query: str, palace_path: str, limit: int) -> dict:
        assert query == "星星"
        assert palace_path == "/tmp/palace"
        assert limit == 2
        return {
            "results": [
                {
                    "text": "我们前天讨论过星星和银河，还提到夜空对你的意义。",
                    "wing": "wing_xiaoyan",
                    "room": "relationship",
                    "similarity": 0.91,
                },
                {
                    "text": "你希望我主动时保持低压和真诚。",
                    "wing": "wing_xiaoyan",
                    "room": "preferences",
                    "similarity": 0.87,
                },
            ]
        }

    adapter = MemPalaceAdapter(
        enabled=True,
        palace_path="/tmp/palace",
        results_limit=2,
        search_backend=_stub_search,
    )

    rendered = adapter.search_context("星星")

    assert "【长期记忆检索】" in rendered
    assert "wing_xiaoyan/relationship" in rendered
    assert "0.91" in rendered
    assert "你希望我主动时保持低压和真诚" in rendered


def test_mempalace_adapter_search_gracefully_degrades_on_error():
    def _broken_search(query: str, palace_path: str, limit: int) -> dict:
        raise RuntimeError("boom")

    adapter = MemPalaceAdapter(
        enabled=True,
        palace_path="/tmp/palace",
        search_backend=_broken_search,
    )

    assert adapter.search_context("hello") == ""


def test_mempalace_adapter_record_exchange_returns_false_when_message_is_blank():
    adapter = MemPalaceAdapter()
    assert adapter.record_exchange("   ", "hello", "assistant_1") is False


def test_mempalace_adapter_record_exchange_calls_write_backend():
    captured: dict[str, str] = {}

    def _stub_write(*, content: str, source_context: str, session_id: str | None) -> bool:
        captured["content"] = content
        captured["source_context"] = source_context
        captured["session_id"] = session_id or ""
        return True

    adapter = MemPalaceAdapter(
        enabled=True,
        palace_path="/tmp/palace",
        write_backend=_stub_write,
    )

    result = adapter.record_exchange("你还记得星星吗", "我记得", "assistant_42")

    assert result is True
    assert captured["content"].startswith("> 你还记得星星吗")
    assert "我记得" in captured["content"]
    assert captured["source_context"] == "xiaoyan_chat_exchange"
    assert captured["session_id"] == "assistant_42"


def test_mempalace_adapter_does_not_fallback_to_local_history_when_write_backend_fails():
    def _broken_write(*, content: str, source_context: str, session_id: str | None) -> bool:
        raise RuntimeError("write unavailable")

    adapter = MemPalaceAdapter(
        enabled=True,
        palace_path="/tmp/palace",
        write_backend=_broken_write,
    )

    result = adapter.record_exchange("hello", "world", "assistant_local_1")

    assert result is False
    recent = adapter.list_recent_chat_messages(limit=2, offset=0)
    assert recent == []
