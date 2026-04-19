import os
from pathlib import Path

from app.config_llm import (
    LLMProviderConfig,
    get_chat_model,
    get_chat_provider,
    get_llm_provider_configs,
)


def load_local_env() -> None:
    service_root = Path(__file__).resolve().parents[1]
    candidates = [Path.cwd() / ".env.local", service_root / ".env.local"]
    seen_paths: set[Path] = set()

    for path in candidates:
        if path in seen_paths or not path.exists():
            continue

        seen_paths.add(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if not item or item.startswith("#") or "=" not in item:
                continue

            key, value = item.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_service_root() -> Path:
    return Path(__file__).resolve().parents[1]

def get_world_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("WORLD_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "world.json"


def get_state_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("STATE_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "state.json"


def get_persona_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("PERSONA_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "persona.json"

def get_capability_queue_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("CAPABILITY_QUEUE_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()
    return get_service_root() / ".data" / "capability_queue.json"


def _read_positive_float_env(name: str, default: float, *, minimum: float) -> float:
    load_local_env()
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _read_positive_int_env(name: str, default: int, *, minimum: int) -> int:
    load_local_env()
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)

def get_chat_context_limit() -> int:
    """获取聊天记忆预算基线（会映射为近期对话预算与长期检索命中数）。"""
    load_local_env()
    configured = os.getenv("CHAT_CONTEXT_LIMIT")
    if configured:
        try:
            value = int(configured)
            return max(1, min(20, value))  # 限制在 1-20 之间
        except ValueError:
            pass
    return 6  # 默认聊天记忆预算基线


def get_chat_read_timeout_seconds() -> int:
    """获取上游聊天模型读取超时时间（秒），适用于流式读取与工具链路等待。"""
    load_local_env()
    configured = os.getenv("CHAT_READ_TIMEOUT_SECONDS", "").strip()
    if configured:
        try:
            value = int(configured)
            return max(10, min(600, value))
        except ValueError:
            pass
    return 180


def get_mempalace_palace_path() -> str:
    load_local_env()
    service_root = Path(__file__).resolve().parents[1]
    default_path = service_root / ".mempalace" / "palace"
    configured = os.getenv("MEMPALACE_PALACE_PATH", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = service_root / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(service_root)
        except ValueError:
            return str(default_path)
        return str(candidate)
    return str(default_path)


def get_mempalace_results_limit() -> int:
    load_local_env()
    configured = os.getenv("MEMPALACE_RESULTS_LIMIT", "").strip()
    if configured:
        try:
            value = int(configured)
            return max(1, min(10, value))
        except ValueError:
            pass
    return 3


def get_mempalace_wing() -> str:
    load_local_env()
    configured = os.getenv("MEMPALACE_WING", "").strip()
    return configured or "wing_xiaoyan"


def get_mempalace_room() -> str:
    load_local_env()
    configured = os.getenv("MEMPALACE_ROOM", "").strip()
    return configured or "chat_exchange"
