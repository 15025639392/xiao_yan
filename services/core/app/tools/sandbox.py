class CommandSandbox:
    def __init__(self, allowed_commands: set[str]) -> None:
        self.allowed_commands = allowed_commands

    def validate(self, command: str) -> str:
        executable = command.strip().split()[0]
        if executable not in self.allowed_commands:
            raise PermissionError(f"command not allowed: {executable}")
        return command
