import asyncio

from starlette.websockets import WebSocketDisconnect

from app.realtime import AppRealtimeHub


class _DisconnectOnSnapshotSocket:
    async def accept(self) -> None:
        return None

    async def send_json(self, payload) -> None:  # noqa: ANN001
        raise WebSocketDisconnect(code=1006)


def test_connect_returns_false_when_client_disconnects_during_snapshot():
    loop = asyncio.new_event_loop()
    try:
        hub = AppRealtimeHub(
            loop=loop,
            snapshot_builder=lambda: {"runtime": {}, "memory": {}, "persona": {}},
        )
        socket = _DisconnectOnSnapshotSocket()

        connected = asyncio.run(hub.connect(socket))

        assert connected is False
        assert socket not in hub._connections
    finally:
        loop.close()
