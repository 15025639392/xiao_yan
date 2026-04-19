from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.capabilities_routes import build_capabilities_router
from app.api.chat_routes import build_chat_router
from app.api.config_routes import build_config_router
from app.api.memory_routes import build_memory_router
from app.api.persona_routes import build_persona_router
from app.api.runtime_routes import build_runtime_router
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
        r"(^https?://("
        r"localhost"
        r"|127\.0\.0\.1"
        r"|0\.0\.0\.0"
        r"|10(?:\.\d{1,3}){3}"
        r"|192\.168(?:\.\d{1,3}){2}"
        r"|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
        r")(:\d+)?$)"
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
app.include_router(build_chat_router())
app.include_router(build_config_router())
app.include_router(build_capabilities_router())
app.include_router(build_persona_router())
app.include_router(build_memory_router())
app.include_router(build_tools_router())
