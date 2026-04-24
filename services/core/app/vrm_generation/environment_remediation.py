from __future__ import annotations

from pathlib import Path

from app.capabilities.models import CapabilityContext, CapabilityDispatchRequest, RiskLevel
from app.capabilities.runtime import dispatch_capability_request

BLENDER_INSTALL_COMMAND = "brew install --cask blender"
HOMEBREW_DOWNLOAD_COMMAND = (
    "curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh "
    "-o /tmp/xiaoyan-homebrew-install.sh"
)
HOMEBREW_INSTALL_COMMAND = "bash /tmp/xiaoyan-homebrew-install.sh"
HOMEBREW_CANDIDATES = (
    Path("/opt/homebrew/bin/brew"),
    Path("/usr/local/bin/brew"),
)


def request_blender_install_remediation(*, job_id: str) -> str:
    """Queue a user-approved environment repair when Blender is missing."""
    if not _homebrew_available():
        return request_homebrew_install_remediation(job_id=job_id)

    record = dispatch_capability_request(
        CapabilityDispatchRequest(
            capability="shell.run",
            args={
                "command": BLENDER_INSTALL_COMMAND,
                "timeout_seconds": 120,
            },
            risk_level=RiskLevel.RESTRICTED,
            requires_approval=True,
            idempotency_key=f"environment:macos:install-blender:{job_id}",
            max_attempts=1,
            context=CapabilityContext(
                reason=(
                    "VRM 形象生成需要 Blender，但当前 Mac 未配置可用的 Blender。"
                    f"小晏已准备通过 Homebrew 安装 Blender；来源任务：{job_id}。"
                )
            ),
        )
    )
    return record.request.request_id


def request_homebrew_install_remediation(*, job_id: str) -> str:
    download = _dispatch_shell_step(
        command=HOMEBREW_DOWNLOAD_COMMAND,
        idempotency_key=f"environment:macos:download-homebrew-installer:{job_id}",
        reason=(
            "VRM 形象生成需要 Blender，但当前 Mac 还没有 Homebrew，无法继续安装 Blender。"
            f"小晏先准备下载 Homebrew 官方安装脚本；来源任务：{job_id}。"
        ),
    )
    _dispatch_shell_step(
        command=HOMEBREW_INSTALL_COMMAND,
        idempotency_key=f"environment:macos:install-homebrew:{job_id}",
        reason=(
            "Homebrew 官方安装脚本下载后，小晏准备执行它来补齐 Mac 包管理器。"
            f"完成后需要重新触发 VRM 生成以继续安装 Blender；来源任务：{job_id}。"
        ),
    )
    return download


def _dispatch_shell_step(*, command: str, idempotency_key: str, reason: str) -> str:
    record = dispatch_capability_request(
        CapabilityDispatchRequest(
            capability="shell.run",
            args={
                "command": command,
                "timeout_seconds": 120,
            },
            risk_level=RiskLevel.RESTRICTED,
            requires_approval=True,
            idempotency_key=idempotency_key,
            max_attempts=1,
            context=CapabilityContext(reason=reason),
        )
    )
    return record.request.request_id


def _homebrew_available() -> bool:
    return any(candidate.is_file() for candidate in HOMEBREW_CANDIDATES)
