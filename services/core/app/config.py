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
