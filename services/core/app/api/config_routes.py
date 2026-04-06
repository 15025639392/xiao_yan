from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.runtime_ext.runtime_config import get_runtime_config


class ConfigUpdateRequest(BaseModel):
    chat_context_limit: int = Field(..., ge=1, le=20, description="聊天上下文相关事件数量限制（1-20）")


class ConfigResponse(BaseModel):
    chat_context_limit: int


def build_config_router() -> APIRouter:
    router = APIRouter()

    @router.get("/config")
    def get_config() -> ConfigResponse:
        config = get_runtime_config()
        return ConfigResponse(chat_context_limit=config.chat_context_limit)

    @router.put("/config")
    def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
        config = get_runtime_config()
        config.chat_context_limit = request.chat_context_limit
        return ConfigResponse(chat_context_limit=config.chat_context_limit)

    return router
