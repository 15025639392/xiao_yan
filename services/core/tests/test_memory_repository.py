import json
from pathlib import Path

from app.memory.models import MemoryEvent
from app.memory.repository import FileMemoryRepository, InMemoryMemoryRepository


def test_repository_saves_event_and_returns_recent_items():
    repo = InMemoryMemoryRepository()
    event = MemoryEvent(kind="episode", content="她在醒来后主动问候用户")
    repo.save_event(event)
    recent = repo.list_recent(limit=5)
    assert recent[0].content == "她在醒来后主动问候用户"
    assert recent[0].entry_id == event.entry_id


def test_file_repository_persists_events_across_instances(tmp_path: Path):
    storage_path = tmp_path / "memory.jsonl"

    writer = FileMemoryRepository(storage_path)
    writer.save_event(
        MemoryEvent(
            kind="chat",
            role="user",
            content="你好，小燕",
        )
    )

    reader = FileMemoryRepository(storage_path)
    recent = reader.list_recent(limit=5)

    assert recent[0].kind == "chat"
    assert recent[0].role == "user"
    assert recent[0].content == "你好，小燕"


def test_in_memory_repository_returns_relevant_events_before_irrelevant_recent_ones():
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="我们讨论过星星和夜空"))
    repo.save_event(MemoryEvent(kind="chat", role="assistant", content="后来又聊了早餐"))
    repo.save_event(MemoryEvent(kind="chat", role="user", content="今天想整理文件"))

    relevant = repo.search_relevant("还记得星星吗", limit=2)

    assert [event.content for event in relevant] == [
        "我们讨论过星星和夜空",
        "后来又聊了早餐",
    ]


def test_file_repository_physically_purges_rows_without_entry_id(tmp_path: Path):
    storage_path = tmp_path / "memory.jsonl"
    storage_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "world",
                        "content": "invalid row",
                        "role": None,
                        "created_at": "2026-04-05T11:03:23.458102Z",
                        "entry_id": None,
                    },
                    ensure_ascii=False,
                ),
                MemoryEvent(kind="chat", role="user", content="valid row").model_dump_json(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    repo = FileMemoryRepository(storage_path)
    recent = repo.list_recent(limit=10)

    assert [event.content for event in recent] == ["valid row"]

    rewritten_lines = [line for line in storage_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rewritten_lines) == 1
    assert json.loads(rewritten_lines[0])["content"] == "valid row"
