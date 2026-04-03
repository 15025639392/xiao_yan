import pytest

from app.tools.sandbox import CommandSandbox


def test_sandbox_allows_whitelisted_command():
    sandbox = CommandSandbox(allowed_commands={"pwd"})
    result = sandbox.validate("pwd")
    assert result == "pwd"


def test_sandbox_blocks_non_whitelisted_command():
    sandbox = CommandSandbox(allowed_commands={"pwd"})
    with pytest.raises(PermissionError):
        sandbox.validate("rm -rf /")
