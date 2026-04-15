from app.memory.models import MemoryKind
from app.memory.repository import InMemoryMemoryRepository
from app.memory.service import MemoryService


class TrackingRepository(InMemoryMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []

    def list_recent(
        self,
        limit: int,
        offset: int = 0,
        *,
        status: str = "active",
        kind: str | None = None,
        namespace: str | None = None,
        visibility: str | None = None,
        query: str | None = None,
    ):
        self.calls.append(
            {
                "limit": limit,
                "offset": offset,
                "status": status,
                "kind": kind,
                "namespace": namespace,
                "visibility": visibility,
                "query": query,
            }
        )
        return super().list_recent(
            limit=limit,
            offset=offset,
            status=status,  # type: ignore[arg-type]
            kind=kind,
            namespace=namespace,
            visibility=visibility,  # type: ignore[arg-type]
            query=query,
        )


def test_list_recent_does_not_overfetch_without_multi_kind_filter() -> None:
    repo = TrackingRepository()
    service = MemoryService(repository=repo)

    service.list_recent(limit=200, offset=5)

    assert repo.calls[-1]["limit"] == 200
    assert repo.calls[-1]["offset"] == 5
    assert repo.calls[-1]["kind"] is None


def test_list_recent_overfetches_when_multi_kind_filter_is_used() -> None:
    repo = TrackingRepository()
    service = MemoryService(repository=repo)

    service.list_recent(limit=50, kinds=[MemoryKind.FACT, MemoryKind.EPISODIC])

    assert repo.calls[-1]["limit"] == 150
    assert repo.calls[-1]["kind"] is None

