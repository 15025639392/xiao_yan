"""Command Sandbox — 安全命令执行层。"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from app.tools.sandbox_registry import (
    DEFAULT_TOOL_REGISTRY,
    ToolMetadata,
    ToolSafetyLevel,
    get_default_allowed_commands,
)

# ── 危险模式检测 ──────────────────────────────────────

# shell 元字符序列，用于注入攻击
_SHELL_INJECTION_PATTERNS = [
    r";",           # 命令链: cmd; evil
    r"\|",          # 管道: cmd | evil
    r"&",           # 后台/并行: cmd & evil
    r"\$\(",        # 命令替换: $(cmd)
    r"`",           # 反引号替换: `cmd`
    r">\s*/",       # 重写到根: > /etc/passwd
    r"<\s*/",       # 从根读取: < /etc/passwd
    r"\.\./",       # 路径遍历: ../
    r"rm\s+-rf",    # 强制删除: rm -rf /
    r"chmod\s+",    # 权限修改: chmod 777
    r">\s*\S+\.ssh", # 写入 ssh 目录
    r"/dev/sd[a-z]",# 磁盘设备
    r"mkfs",        # 格式化
    r"dd\s+if=",    # 磁盘写入
    r":\(\)\s*\{",  # fork bomb
    r"curl.*\|.*sh", # 远程脚本执行
    r"wget.*\|.*sh",
    r"eval\s+",     # eval 执行
    r"exec\s+",     # exec 替换
]

_COMPILED_INJECTION_RE = [
    re.compile(p) for p in _SHELL_INJECTION_PATTERNS
]


# ── 危险参数黑名单（部分命令专用） ────────────────────

_DANGEROUS_ARGS = {
    "rm": [r"--no-preserve-root", r"-rf\s+/", r"-rf\s+/"],
    "python": [],  # python 本身安全，参数由沙箱环境控制
    "pip": ["install", "--force-reinstall"],  # 防止意外覆盖系统包
}


# ── 主类 ────────────────────────────────────────────────


class SandboxViolation(ValueError):
    """沙箱违规异常"""
    def __init__(self, message: str, violation_type: str = "unknown") -> None:
        super().__init__(message)
        self.violation_type = violation_type


class CommandSandbox:
    """命令沙箱。"""

    def __init__(
        self,
        allowed_tool_names: set[str],
        *,
        allow_shell_injection: bool = False,
        allow_path_traversal: bool = False,
        allowed_base_path: Path | None = None,
        block_dangerous_args: bool = True,
    ) -> None:
        """
        Args:
            allowed_tool_names: 允许的命令集合。
            allow_shell_injection: 是否允许 shell 注入字符（生产环境必须 False）
            allow_path_traversal: 是否允许 ../ 路径遍历
            allowed_base_path: 限制的工作目录基准路径（None 不限制）
            block_dangerous_args: 是否拦截已知的危险参数组合
        """
        self.allowed_commands = allowed_tool_names
        self.allow_shell_injection = allow_shell_injection
        self.allow_path_traversal = allow_path_traversal
        self.allowed_base_path = allowed_base_path
        self.block_dangerous_args = block_dangerous_args

    @classmethod
    def with_defaults(
        cls,
        max_level: ToolSafetyLevel = ToolSafetyLevel.RESTRICTED,
        allowed_base_path: Path | None = None,
    ) -> "CommandSandbox":
        """用默认工具注册表创建沙箱实例。

        Args:
            max_level: 最高允许的安全级别
                - SAFE: 只有 pwd/ls/cat 等纯只读
                - RESTRICTED: 加上 git/python/pip/make 等开发工具
                - DANGEROUS: 再加上 curl/wget/rm 等需谨慎使用的
            allowed_base_path: 限制的工作目录
        """
        return cls(
            allowed_tool_names=get_default_allowed_commands(max_level),
            allowed_base_path=allowed_base_path,
        )

    def validate(self, command: str) -> str:
        """验证命令字符串，返回清理后的合法命令。

        Raises:
            PermissionError: 命令不在白名单中
            SandboxViolation: 检测到注入攻击或其他安全问题
        """
        stripped = command.strip()
        if not stripped:
            raise SandboxViolation("空命令", "empty_command")

        # 1. 提取可执行名称
        executable = self._extract_executable(stripped)

        # 2. 白名单检查
        if executable not in self.allowed_commands:
            raise PermissionError(f"command not allowed: {executable}")

        # 3. 工具级安全检查
        tool_meta = DEFAULT_TOOL_REGISTRY.get(executable)
        if tool_meta is not None and tool_meta.safety_level == ToolSafetyLevel.BLOCKED:
            raise SandboxViolation(
                f"command permanently blocked: {executable}",
                "blocked_command",
            )

        # 4. Shell 注入检测
        if not self.allow_shell_injection:
            self._check_shell_injection(stripped)

        # 5. 路径遍历检测
        if not self.allow_path_traversal:
            self._check_path_traversal(stripped)

        # 6. 危险参数检测
        if self.block_dangerous_args:
            self._check_dangerous_args(executable, stripped)

        return stripped

    def get_tool_metadata(self, command_name: str) -> ToolMetadata | None:
        """查询工具的元数据。"""
        return DEFAULT_TOOL_REGISTRY.get(command_name)

    def list_available_tools(
        self, category: str | None = None, level: ToolSafetyLevel | None = None,
    ) -> list[ToolMetadata]:
        """列出当前可用工具（可选按类别/级别过滤）。"""
        tools = []
        for name, meta in DEFAULT_TOOL_REGISTRY.items():
            if name not in self.allowed_commands:
                continue
            if category is not None and meta.category != category:
                continue
            if level is not None and meta.safety_level != level:
                continue
            tools.append(meta)
        return sorted(tools, key=lambda t: t.name)

    def _extract_executable(self, command: str) -> str:
        """从命令字符串中提取可执行程序名。"""
        try:
            tokens = shlex.split(command)
        except ValueError:
            # 引号不匹配等情况，回退到简单分割
            tokens = command.split()

        if not tokens:
            return ""

        exec_name = tokens[0]
        # 处理绝对路径: /bin/ls -> ls
        if "/" in exec_name:
            exec_name = Path(exec_name).name
        return exec_name

    def _check_shell_injection(self, command: str) -> None:
        """检测 shell 注入模式。"""
        # 排除引号内的内容后检查（简化版：整体扫描）
        for pattern in _COMPILED_INJECTION_RE:
            if pattern.search(command):
                raise SandboxViolation(
                    f"potential shell injection detected (pattern matched): "
                    f"{command[:100]}",
                    "shell_injection",
                )

    def _check_path_traversal(self, command: str) -> None:
        """检测危险的路径遍历。"""
        if "../" in command or "..\\" in command:
            # 允许相对父目录但限制深度
            depth = command.count("../") + command.count("..\\")
            if depth > 3:
                raise SandboxViolation(
                    f"path traversal too deep ({depth} levels)",
                    "path_traversal",
                )

        # 检查是否尝试访问敏感目录
        _SENSITIVE_PATHS = [
            "/etc/shadow", "/etc/passwd", ".ssh/", ".env.local",
            "~/.ssh/", "/.ssh/",
        ]
        lower_cmd = command.lower()
        for sensitive in _SENSITIVE_PATHS:
            if sensitive.lower() in lower_cmd:
                raise SandboxViolation(
                    f"access to sensitive path blocked: {sensitive}",
                    "sensitive_path",
                )

    def _check_dangerous_args(self, executable: str, command: str) -> None:
        """检测特定命令的危险参数组合。"""
        dangerous_patterns = _DANGEROUS_ARGS.get(executable, [])
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                raise SandboxViolation(
                    f"dangerous argument combination blocked for {executable}: {pattern}",
                    "dangerous_args",
                )
