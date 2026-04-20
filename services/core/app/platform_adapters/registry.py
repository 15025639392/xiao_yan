from __future__ import annotations

from app.platform_adapters.adapters import (
    WechatManualAdapter,
    WechatOfficialAdapter,
    XiaohongshuAdapter,
)
from app.platform_adapters.protocol import PlatformAdapter


class PlatformAdapterRegistry:
    def __init__(self, adapters: list[PlatformAdapter]) -> None:
        self._adapters = {adapter.platform: adapter for adapter in adapters}

    def get(self, platform: str) -> PlatformAdapter:
        try:
            return self._adapters[platform]
        except KeyError as exc:
            raise ValueError(f"unsupported platform adapter: {platform}") from exc

    def list_platforms(self) -> list[str]:
        return sorted(self._adapters.keys())


def build_platform_adapter_registry() -> PlatformAdapterRegistry:
    return PlatformAdapterRegistry(
        adapters=[
            WechatManualAdapter(),
            XiaohongshuAdapter(),
            WechatOfficialAdapter(),
        ]
    )
