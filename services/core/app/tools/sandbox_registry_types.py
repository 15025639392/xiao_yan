"""命令沙箱注册表类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolSafetyLevel(str, Enum):
    """工具安全等级（数值越大越危险）"""

    SAFE = "safe"
    RESTRICTED = "restricted"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"

    @property
    def rank(self) -> int:
        order = {self.SAFE: 0, self.RESTRICTED: 1, self.DANGEROUS: 2, self.BLOCKED: 3}
        return order[self]


@dataclass(frozen=True)
class ToolMetadata:
    """工具元数据"""

    name: str
    description: str
    safety_level: ToolSafetyLevel
    category: str
    examples: list[str] = field(default_factory=list)
    max_timeout_seconds: float = 30.0
