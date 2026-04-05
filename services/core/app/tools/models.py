from pydantic import BaseModel


class ToolExecutionResult(BaseModel):
    command: str
    output: str = ""
    stderr: str = ""
    exit_code: int = -1
    success: bool = False
    timed_out: bool = False
    truncated: bool = False
    duration_seconds: float = 0.0
    executed_at: str = ""
    tool_name: str | None = None
    safety_level: str | None = None
    working_directory: str = ""
    error: str | None = None

    @property
    def summary(self) -> str:
        status = "OK" if self.success else ("TIMEOUT" if self.timed_out else f"ERR({self.exit_code})")
        trunc_marker = " [truncated]" if self.truncated else ""
        return f"[{status}] {self.duration_seconds:.2f}s -> {len(self.output)}B{trunc_marker}"

    def to_dict(self) -> dict:
        return self.model_dump()
