#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
IGNORED_DIR_NAMES = {"__pycache__", "node_modules", ".git", ".venv", ".pytest_cache"}


def iter_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        yield path


def count_files(root: Path, suffixes: set[str] | None = None) -> int:
    total = 0
    for path in iter_files(root):
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        total += 1
    return total


def list_children(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and path.name not in IGNORED_DIR_NAMES
    )


def scan() -> dict[str, object]:
    service_app = REPO_ROOT / "services/core/app"
    desktop_src = REPO_ROOT / "apps/desktop/src"
    docs_root = REPO_ROOT / "docs"
    scripts_root = REPO_ROOT / "services/core/scripts"

    hot_dirs = {
        "service_domains": list_children(service_app),
        "desktop_component_groups": list_children(desktop_src / "components"),
    }

    heavy_signals = {
        "orchestrator_present": (service_app / "orchestrator").exists(),
        "self_programming_present": (service_app / "self_programming").exists(),
        "memory_present": (service_app / "memory").exists(),
        "mcp_present": (service_app / "mcp").exists(),
        "docs_requirements_present": (docs_root / "requirements").exists(),
        "docs_checkpoints_present": (docs_root / "checkpoints").exists(),
    }

    counts = {
        "backend_python_files": count_files(service_app, {".py"}),
        "frontend_tsx_ts_files": count_files(desktop_src, {".ts", ".tsx"}),
        "core_scripts": count_files(scripts_root, {".py", ".sh"}),
        "requirement_docs": count_files(docs_root / "requirements", {".md"}),
        "checkpoint_docs": count_files(docs_root / "checkpoints", {".md"}),
        "plan_docs": count_files(docs_root / "plans", {".md"}),
    }

    return {
        "repo_root": str(REPO_ROOT),
        "counts": counts,
        "hot_dirs": hot_dirs,
        "heavy_signals": heavy_signals,
        "simplify_first": [
            "default navigation and default routes",
            "backend modules not required by chat/runtime",
            "optional heavy dependencies in memory and self-programming paths",
            "non-essential scripts under services/core/scripts",
            "historical requirement/checkpoint documents if they slow understanding",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(scan(), ensure_ascii=False, indent=2))
