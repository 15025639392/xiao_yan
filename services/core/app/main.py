from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.capabilities_routes import build_capabilities_router
from app.api.chat_routes import build_chat_router
from app.api.config_routes import build_config_router
from app.api.memory_routes import build_memory_router
from app.api.orchestrator_routes import build_orchestrator_router
from app.api.persona_routes import build_persona_router
from app.api.runtime_routes import build_runtime_router
from app.api.self_programming_routes import build_self_programming_router
from app.api.tools_routes import build_tools_router
from app.api.world_routes import build_world_router
from app.runtime_ext.bootstrap import ensure_runtime_initialized, shutdown_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_runtime_initialized(app)
    try:
        yield
    finally:
        shutdown_runtime(app)


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_origin_regex=(
        r"(^https?://(localhost|127\.0\.0\.1)(:\d+)?$)"
        r"|(^null$)"
        r"|(^tauri://localhost$)"
        r"|(^capacitor://localhost$)"
        r"|(^ionic://localhost$)"
        r"|(^app://.+$)"
        r"|(^electron://.+$)"
    ),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_runtime_router())
app.include_router(build_world_router())
app.include_router(build_capabilities_router())
app.include_router(build_chat_router())
app.include_router(build_self_programming_router())
app.include_router(build_orchestrator_router())
app.include_router(build_config_router())
app.include_router(build_persona_router())
app.include_router(build_memory_router())
app.include_router(build_tools_router())

# Backwards-compatible exports for tests and any legacy imports:
# re-export the *same* dependency callables used by routers so dependency overrides keep working.
from app.api.deps import (  # noqa: E402
    get_chat_gateway,
    get_goal_admission_service,
    get_goal_repository,
    get_memory_repository,
    get_memory_service,
    get_orchestrator_conversation_service,
    get_orchestrator_service,
    get_morning_plan_draft_generator,
    get_morning_plan_planner,
    get_persona_service,
    get_state_store,
    get_world_repository,
    get_world_state_service,
)


def _ensure_runtime_initialized(target_app: FastAPI | None = None) -> None:
    ensure_runtime_initialized(app if target_app is None else target_app)
