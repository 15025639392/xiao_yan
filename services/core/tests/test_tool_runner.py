from app.tools.runner import CommandRunner
from app.tools.sandbox import CommandSandbox


def test_command_runner_executes_whitelisted_command():
    runner = CommandRunner(CommandSandbox(allowed_commands={"pwd"}))

    result = runner.run("pwd")

    assert result.command == "pwd"
    assert result.output

