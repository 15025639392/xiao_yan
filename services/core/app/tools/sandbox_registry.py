"""命令沙箱的工具注册表导出与查询函数。"""

from __future__ import annotations

from app.tools.sandbox_registry_defaults import DEFAULT_TOOL_REGISTRY
from app.tools.sandbox_registry_types import ToolMetadata, ToolSafetyLevel


def get_default_allowed_commands(safety_filter: ToolSafetyLevel | None = None) -> set[str]:
    """获取默认白名单（可选按安全级别过滤）。"""
    if safety_filter is None:
        return set(DEFAULT_TOOL_REGISTRY.keys())
    return {
        name
        for name, meta in DEFAULT_TOOL_REGISTRY.items()
        if meta.safety_level.rank <= safety_filter.rank
        and meta.safety_level != ToolSafetyLevel.BLOCKED
    }


__all__ = [
    "ToolSafetyLevel",
    "ToolMetadata",
    "DEFAULT_TOOL_REGISTRY",
    "get_default_allowed_commands",
]
