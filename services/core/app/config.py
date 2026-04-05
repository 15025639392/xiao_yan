import os
from pathlib import Path


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


def get_memory_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("MEMORY_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "memory.jsonl"


def get_goal_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("GOAL_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "goals.json"


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


def is_morning_plan_llm_enabled() -> bool:
    load_local_env()
    return os.getenv("MORNING_PLAN_LLM_ENABLED", "").lower() in {"1", "true", "yes", "on"}
