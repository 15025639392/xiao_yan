from app.mcp.service import build_chat_mcp_tool_registry


def test_build_chat_mcp_tool_registry_skips_initialization_for_empty_selection(monkeypatch):
    class _ShouldNotConstructClient:  # pragma: no cover - used to fail the test if constructed
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("StdioMcpClient should not be initialized when selection is empty")

    monkeypatch.setattr("app.mcp.service.StdioMcpClient", _ShouldNotConstructClient)

    registry = build_chat_mcp_tool_registry(
        mcp_enabled=True,
        configured_servers=[
            {
                "server_id": "filesystem",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "enabled": True,
                "timeout_seconds": 20,
            }
        ],
        selected_server_ids=[],
    )

    assert registry.tools == []
    assert registry.tool_to_server == {}


def test_build_chat_mcp_tool_registry_initializes_enabled_servers_when_selection_is_none(monkeypatch):
    init_commands: list[str] = []

    class _FakeClient:
        def __init__(self, *, command, args=None, cwd=None, env=None, timeout_seconds=20) -> None:  # noqa: ANN001
            init_commands.append(command)

        def initialize(self) -> None:
            return None

        def list_tools(self):
            return [
                {
                    "name": "echo_tool",
                    "description": "echo",
                    "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
                }
            ]

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.mcp.service.StdioMcpClient", _FakeClient)

    registry = build_chat_mcp_tool_registry(
        mcp_enabled=True,
        configured_servers=[
            {
                "server_id": "filesystem",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "enabled": True,
                "timeout_seconds": 20,
            }
        ],
        selected_server_ids=None,
    )

    assert init_commands == ["npx"]
    assert len(registry.tools) == 1
    assert registry.tools[0]["name"] == "mcp__filesystem__echo_tool"
    assert "mcp__filesystem__echo_tool" in registry.tool_to_server
