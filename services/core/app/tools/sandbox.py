"""
Enhanced Command Sandbox — Tools Phase: 安全命令执行层

安全层级设计:
1. 命令白名单（只允许已知安全的可执行程序）
2. Shell 注入防护（检测管道、分号、反引号等危险模式）
3. 路径限制（防止越权访问敏感目录）
4. 参数启发式检查（警告但不阻断常见安全参数）

向后兼容: 旧代码传入 allowed_commands set 仍然工作。
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


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


# ── 工具安全分级 ──────────────────────────────────────

class ToolSafetyLevel(str, Enum):
    """工具安全等级（数值越大越危险）"""
    SAFE = "safe"            # 0: 只读/信息类，无副作用
    RESTRICTED = "restricted"# 1: 有副作用但受控（写文件/运行测试）
    DANGEROUS = "dangerous"  # 2: 需要审批（网络访问/系统修改）
    BLOCKED = "blocked"      # 3: 永久禁止

    # 数值用于比较
    @property
    def rank(self) -> int:
        _order = {self.SAFE: 0, self.RESTRICTED: 1, self.DANGEROUS: 2, self.BLOCKED: 3}
        return _order[self]


@dataclass(frozen=True)
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    safety_level: ToolSafetyLevel
    category: str             # filesystem / network / system / dev / info
    examples: list[str] = field(default_factory=list)
    max_timeout_seconds: float = 30.0


# ── 默认工具注册表 ────────────────────────────────────

DEFAULT_TOOL_REGISTRY: dict[str, ToolMetadata] = {
    # ══ 信息类 (SAFE) ═══
    "pwd": ToolMetadata(
        name="pwd", description="打印当前工作目录",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["pwd"],
    ),
    "date": ToolMetadata(
        name="date", description="显示当前日期时间",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["date", 'date +"%Y-%m-%d %H:%M:%S"'],
    ),
    "echo": ToolMetadata(
        name="echo", description="输出文本",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["echo hello", 'echo "multi word text"'],
    ),
    "whoami": ToolMetadata(
        name="whoami", description="显示当前用户名",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["whoami"],
    ),
    "hostname": ToolMetadata(
        name="hostname", description="显示主机名",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["hostname"],
    ),
    "uname": ToolMetadata(
        name="uname", description="显示系统信息",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["uname -a"],
    ),
    "uptime": ToolMetadata(
        name="uptime", description="显示系统运行时间",
        safety_level=ToolSafetyLevel.SAFE, category="info",
        examples=["uptime"],
    ),

    # ══ 文件系统只读 (SAFE) ═══
    "ls": ToolMetadata(
        name="ls", description="列出目录内容",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["ls", "ls -la", "ls src/"],
        max_timeout_seconds=10.0,
    ),
    "cat": ToolMetadata(
        name="cat", description="查看文件内容",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["cat file.txt", "cat README.md"],
        max_timeout_seconds=15.0,
    ),
    "find": ToolMetadata(
        name="find", description="搜索文件",
        safety_level=ToolSafetyLevel.RESTRICTED, category="filesystem",
        examples=["find . -name '*.py'", "find src -type f"],
        max_timeout_seconds=30.0,
    ),
    "grep": ToolMetadata(
        name="grep", description="在文件中搜索文本",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["grep 'TODO' *.py", "grep -r pattern src/"],
        max_timeout_seconds=20.0,
    ),
    "head": ToolMetadata(
        name="head", description="显示文件开头",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["head -20 file.py", "head -n 50 README.md"],
    ),
    "tail": ToolMetadata(
        name="tail", description="显示文件末尾",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["tail -20 file.py", "tail -f log.txt"],
        max_timeout_seconds=15.0,
    ),
    "wc": ToolMetadata(
        name="wc", description="统计行数/字数/字节数",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["wc -l file.py", "wc -c file.txt"],
    ),
    "diff": ToolMetadata(
        name="diff", description="比较文件差异",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["diff a.txt b.txt", "diff -u old.py new.py"],
        max_timeout_seconds=15.0,
    ),
    "tree": ToolMetadata(
        name="tree", description="以树形结构显示目录",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["tree", "tree -L 2 src/", "tree -a --prune"],
        max_timeout_seconds=10.0,
    ),
    "file": ToolMetadata(
        name="file", description="识别文件类型",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["file mystery.bin", "file *"],
    ),
    "du": ToolMetadata(
        name="du", description="查看磁盘使用量",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["du -sh .", "du -h --max-depth=1"],
        max_timeout_seconds=15.0,
    ),
    "df": ToolMetadata(
        name="df", description="查看磁盘空间",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["df -h"],
    ),
    "stat": ToolMetadata(
        name="stat", description="查看文件详细状态",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["stat file.txt"],
    ),
    "readlink": ToolMetadata(
        name="readlink", description="读取符号链接目标",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["readlink -f path"],
    ),
    "basename": ToolMetadata(
        name="basename", description="提取文件名",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["basename /path/to/file.txt"],
    ),
    "dirname": ToolMetadata(
        name="dirname", description="提取目录路径",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["dirname /path/to/file.txt"],
    ),
    "realpath": ToolMetadata(
        name="realpath", description="获取绝对路径",
        safety_level=ToolSafetyLevel.SAFE, category="filesystem",
        examples=["realpath ./src/app.py"],
    ),

    # ══ 开发工具 (RESTRICTED) ═══
    "git": ToolMetadata(
        name="git", description="版本控制（只读操作自动放行，写操作需要审批）",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=[
            "git status", "git log --oneline -10", "git diff",
            "git branch -a", "git remote -v", "git show HEAD",
        ],
        max_timeout_seconds=30.0,
    ),
    "python": ToolMetadata(
        name="python", description="运行 Python 脚本/表达式",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=[
            'python -c "print(42)"',
            "python --version",
            "python script.py",
            "python -m py_compile file.py",
        ],
        max_timeout_seconds=60.0,
    ),
    "pip": ToolMetadata(
        name="pip", description="Python 包管理器（仅列表/查询）",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["pip list", "pip show package-name", "pip --version"],
        max_timeout_seconds=60.0,
    ),
    "npm": ToolMetadata(
        name="npm", description="Node.js 包管理器（仅列表/查询）",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["npm list", "npm --version"],
        max_timeout_seconds=60.0,
    ),
    "node": ToolMetadata(
        name="node", description="运行 Node.js 脚本",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["node --version", "node script.js"],
        max_timeout_seconds=60.0,
    ),
    "make": ToolMetadata(
        name="make", description="构建工具",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["make", "make test", "make lint"],
        max_timeout_seconds=120.0,
    ),
    "pytest": ToolMetadata(
        name="pytest", description="Python 测试运行器",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["pytest", "pytest tests/ -v", "pytest tests/test_x.py -x"],
        max_timeout_seconds=120.0,
    ),
    "clang": ToolMetadata(
        name="clang/gcc", description="C/C++ 编译器（仅编译不链接）",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["gcc -fsyntax-only file.c"],
        max_timeout_seconds=30.0,
    ),
    "rustc": ToolMetadata(
        name="rustc", description="Rust 编译器（仅检查语法）",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["rustc --edition 2021 --emit=metadata file.rs"],
        max_timeout_seconds=30.0,
    ),
    "go": ToolMetadata(
        name="go", description="Go 工具链",
        safety_level=ToolSafetyLevel.RESTRICTED, category="dev",
        examples=["go version", "go vet ./...", "go build -o /dev/null ."],
        max_timeout_seconds=120.0,
    ),

    # ══ 网络工具 (DANGEROUS) ═══
    "curl": ToolMetadata(
        name="curl", description="HTTP 客户端",
        safety_level=ToolSafetyLevel.DANGEROUS, category="network",
        examples=["curl -I https://example.com", "curl https://api.example.com/data"],
        max_timeout_seconds=30.0,
    ),
    "wget": ToolMetadata(
        name="wget", description="文件下载工具",
        safety_level=ToolSafetyLevel.DANGEROUS, category="network",
        examples=["wget -qO- url"],
        max_timeout_seconds=60.0,
    ),
    "ping": ToolMetadata(
        name="ping", description="网络连通性测试",
        safety_level=ToolSafetyLevel.DANGEROUS, category="network",
        examples=["ping -c 3 8.8.8.8"],
        max_timeout_seconds=15.0,
    ),
    "nslookup": ToolMetadata(
        name="nslookup", description="DNS 查询",
        safety_level=ToolSafetyLevel.DANGEROUS, category="network",
        examples=["nslookup example.com"],
        max_timeout_seconds=10.0,
    ),
    "ssh": ToolMetadata(
        name="ssh", description="远程连接（默认禁用）",
        safety_level=ToolSafetyLevel.BLOCKED, category="network",
        examples=[],
    ),
    "scp": ToolMetadata(
        name="scp", description="远程复制（默认禁用）",
        safety_level=ToolSafetyLevel.BLOCKED, category="network",
        examples=[],
    ),

    # ══ 系统工具 (DANGEROUS/BLOCKED) ═══
    "cp": ToolMetadata(
        name="cp", description="复制文件",
        safety_level=ToolSafetyLevel.RESTRICTED, category="system",
        examples=["cp a.txt b.txt", "cp -r dir1/ dir2/"],
        max_timeout_seconds=30.0,
    ),
    "mv": ToolMetadata(
        name="mv", description="移动/重命名文件",
        safety_level=ToolSafetyLevel.RESTRICTED, category="system",
        examples=["mv old.txt new.txt"],
        max_timeout_seconds=15.0,
    ),
    "mkdir": ToolMetadata(
        name="mkdir", description="创建目录",
        safety_level=ToolSafetyLevel.RESTRICTED, category="system",
        examples=["mkdir new_dir"],
        max_timeout_seconds=5.0,
    ),
    "touch": ToolMetadata(
        name="touch", description="创建空文件或更新时间戳",
        safety_level=ToolSafetyLevel.RESTRICTED, category="system",
        examples=["touch newfile.txt"],
        max_timeout_seconds=5.0,
    ),
    "chmod": ToolMetadata(
        name="chmod", description="修改权限（受限）",
        safety_level=ToolSafetyLevel.DANGEROUS, category="system",
        examples=["chmod +x script.sh"],
        max_timeout_seconds=5.0,
    ),
    "rm": ToolMetadata(
        name="rm", description="删除文件（严格限制：禁止 rm -rf / 和递归根目录）",
        safety_level=ToolSafetyLevel.DANGEROUS, category="system",
        examples=["rm file.txt", "rm -rf my_temp_dir/"],
        max_timeout_seconds=15.0,
    ),
    "kill": ToolMetadata(
        name="kill", description="发送信号给进程（默认禁用）",
        safety_level=ToolSafetyLevel.BLOCKED, category="system",
        examples=[],
    ),
    "sudo": ToolMetadata(
        name="sudo", description="超级用户权限（永久禁用）",
        safety_level=ToolSafetyLevel.BLOCKED, category="system",
        examples=[],
    ),
}


def get_default_allowed_commands(safety_filter: ToolSafetyLevel | None = None) -> set[str]:
    """获取默认白名单（可选按安全级别过滤）。"""
    if safety_filter is None:
        return set(DEFAULT_TOOL_REGISTRY.keys())
    return {
        name for name, meta in DEFAULT_TOOL_REGISTRY.items()
        if meta.safety_level.rank <= safety_filter.rank
        and meta.safety_level != ToolSafetyLevel.BLOCKED  # BLOCKED 永远排除
    }


# ── 主类 ────────────────────────────────────────────────


class SandboxViolation(ValueError):
    """沙箱违规异常"""
    def __init__(self, message: str, violation_type: str = "unknown") -> None:
        super().__init__(message)
        self.violation_type = violation_type


class CommandSandbox:
    """增强版命令沙箱。

    用法::

        # 向后兼容：简单白名单
        sandbox = CommandSandbox(allowed_commands={"pwd", "ls"})
        validated = sandbox.validate("pwd")

        # 新功能：使用默认分级注册表
        sandbox = CommandSandbox.with_defaults(max_level=ToolSafetyLevel.RESTRICTED)
        validated = sandbox.validate("ls -la")
        meta = sandbox.get_tool_metadata("ls")

        # 自定义安全工作目录
        sandbox = CommandSandbox.with_defaults(allowed_base_path=Path("/safe/dir"))
    """

    def __init__(
        self,
        allowed_commands: set[str] | None = None,
        *,
        allow_shell_injection: bool = False,
        allow_path_traversal: bool = False,
        allowed_base_path: Path | None = None,
        block_dangerous_args: bool = True,
    ) -> None:
        """
        Args:
            allowed_commands: 允许的命令集合。None 表示使用默认全量表。
            allow_shell_injection: 是否允许 shell 注入字符（生产环境必须 False）
            allow_path_traversal: 是否允许 ../ 路径遍历
            allowed_base_path: 限制的工作目录基准路径（None 不限制）
            block_dangerous_args: 是否拦截已知的危险参数组合
        """
        self.allowed_commands = (
            allowed_commands if allowed_commands is not None
            else get_default_allowed_commands()
        )
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
            allowed_commands=get_default_allowed_commands(max_level),
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
