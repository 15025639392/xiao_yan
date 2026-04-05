import subprocess

from app.domain.models import ActionResult
from app.tools.sandbox import CommandSandbox


class CommandRunner:
    def __init__(self, sandbox: CommandSandbox) -> None:
        self.sandbox = sandbox

    def run(self, command: str) -> ActionResult:
        validated = self.sandbox.validate(command)
        result = subprocess.run(
            validated,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )
        return ActionResult(command=validated, output=result.stdout.strip())
