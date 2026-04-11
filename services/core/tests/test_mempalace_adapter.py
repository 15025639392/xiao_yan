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


def test_mempalace_adapter_search_context_can_exclude_current_room_hits():
    def _stub_search(query: str, palace_path: str, limit: int) -> dict:
        return {
            "results": [
                {
                    "text": "这是最近聊天内容，不应该重复注入。",
                    "wing": "wing_xiaoyan",
                    "room": "chat_exchange",
                    "similarity": 0.99,
                },
                {
                    "text": "这是长期偏好记忆，应该保留。",
                    "wing": "wing_xiaoyan",
                    "room": "preferences",
                    "similarity": 0.86,
                },
            ]
        }

    adapter = MemPalaceAdapter(
        enabled=True,
        palace_path="/tmp/palace",
        room="chat_exchange",
        search_backend=_stub_search,
    )

    rendered = adapter.search_context("测试", exclude_current_room=True)
    assert "chat_exchange" not in rendered
    assert "preferences" in rendered
    assert "长期偏好记忆" in rendered


def test_mempalace_adapter_search_context_returns_empty_when_only_current_room_hits():
    def _stub_search(query: str, palace_path: str, limit: int) -> dict:
        return {
            "results": [
                {
                    "text": "仅命中最近聊天",
                    "wing": "wing_xiaoyan",
                    "room": "chat_exchange",
                    "similarity": 0.96,
                }
            ]
        }

    adapter = MemPalaceAdapter(
        enabled=True,
        palace_path="/tmp/palace",
        room="chat_exchange",
        search_backend=_stub_search,
    )

    assert adapter.search_context("测试", exclude_current_room=True) == ""


def test_mempalace_adapter_build_chat_messages_uses_turn_based_history_limit():
    adapter = MemPalaceAdapter(enabled=True, palace_path="/tmp/palace")
    latest_first_history = [
        {"id": "a6", "role": "assistant", "content": "a6", "created_at": None, "session_id": None},
        {"id": "u6", "role": "user", "content": "u6", "created_at": None, "session_id": None},
        {"id": "a5", "role": "assistant", "content": "a5", "created_at": None, "session_id": None},
        {"id": "u5", "role": "user", "content": "u5", "created_at": None, "session_id": None},
        {"id": "a4", "role": "assistant", "content": "a4", "created_at": None, "session_id": None},
        {"id": "u4", "role": "user", "content": "u4", "created_at": None, "session_id": None},
        {"id": "a3", "role": "assistant", "content": "a3", "created_at": None, "session_id": None},
    ]

    adapter.list_recent_chat_messages = lambda *, limit, offset=0: latest_first_history[:limit]  # type: ignore[method-assign]

    messages = adapter.build_chat_messages("new", limit=3)

    assert len(messages) == 7
    assert [message.content for message in messages[:-1]] == ["u4", "a4", "u5", "a5", "u6", "a6"]
    assert messages[-1].role == "user"
    assert messages[-1].content == "new"


def test_mempalace_adapter_build_chat_messages_stops_when_budget_reached():
    adapter = MemPalaceAdapter(enabled=True, palace_path="/tmp/palace")
    chunk = "长文本" * 100  # around 300 chars
    latest_first_history = [
        {"id": "a3", "role": "assistant", "content": chunk, "created_at": None, "session_id": None},
        {"id": "u3", "role": "user", "content": chunk, "created_at": None, "session_id": None},
        {"id": "a2", "role": "assistant", "content": chunk, "created_at": None, "session_id": None},
        {"id": "u2", "role": "user", "content": chunk, "created_at": None, "session_id": None},
        {"id": "a1", "role": "assistant", "content": chunk, "created_at": None, "session_id": None},
    ]

    adapter.list_recent_chat_messages = lambda *, limit, offset=0: latest_first_history[:limit]  # type: ignore[method-assign]

    messages = adapter.build_chat_messages("new", limit=2)

    # limit=2 -> max 4 historical messages, but token budget (600) keeps only 3.
    assert len(messages) == 4
    assert messages[-1].content == "new"


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


def test_mempalace_adapter_list_recent_chat_messages_keeps_session_id_from_metadata():
    class _FakeCollection:
        def get(self, *, where=None, include=None, limit=None):
            return {
                "ids": ["drawer_1"],
                "documents": ["> 你好\n我在。"],
                "metadatas": [
                    {
                        "wing": "wing_xiaoyan",
                        "room": "chat_exchange",
                        "filed_at": "2026-04-11T00:00:00+00:00",
                        "session_id": "assistant_abc123",
                    }
                ],
            }

    adapter = MemPalaceAdapter(enabled=True, palace_path="/tmp/palace")
    adapter._get_collection = lambda create: _FakeCollection()  # type: ignore[method-assign]

    recent = adapter.list_recent_chat_messages(limit=10, offset=0)

    assert len(recent) == 2
    assert recent[0]["role"] == "assistant"
    assert recent[0]["session_id"] == "assistant_abc123"
    assert recent[1]["role"] == "user"
    assert recent[1]["session_id"] == "assistant_abc123"
