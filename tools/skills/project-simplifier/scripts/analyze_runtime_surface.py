#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
APP_TSX = REPO_ROOT / "apps/desktop/src/App.tsx"
API_DIR = REPO_ROOT / "services/core/app/api"
PAGES_DIR = REPO_ROOT / "apps/desktop/src/pages"

APP_ROUTE_PATTERN = re.compile(r'"([^"]+)"')
PAGE_IMPORT_PATTERN = re.compile(r'import\s+\{\s*([A-Za-z0-9_,\s]+)\s*\}\s+from\s+"(\./pages/[^"]+)"')
ROUTER_PATTERN = re.compile(r'@router\.(get|post|put|delete|patch)\("([^"]+)"')


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_app_routes() -> list[str]:
    if not APP_TSX.exists():
        return []
    content = _read(APP_TSX)
    match = re.search(r"type AppRoute =(?P<body>.*?);", content, flags=re.S)
    if not match:
        return []
    return [
        token
        for token in APP_ROUTE_PATTERN.findall(match.group("body"))
        if token and token not in {"dark", "light"}
    ]


def extract_page_imports() -> list[dict[str, str]]:
    if not APP_TSX.exists():
        return []
    content = _read(APP_TSX)
    page_imports: list[dict[str, str]] = []
    for names, source in PAGE_IMPORT_PATTERN.findall(content):
        for raw_name in names.split(","):
            name = raw_name.strip()
            if not name:
                continue
            if name.startswith("type "):
                continue
            page_imports.append({"name": name, "source": source})
    return page_imports


def extract_api_routes() -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    if not API_DIR.exists():
        return routes
    for path in sorted(API_DIR.glob("*_routes.py")):
        content = _read(path)
        for method, route in ROUTER_PATTERN.findall(content):
            routes.append({"file": str(path.relative_to(REPO_ROOT)), "method": method.upper(), "path": route})
    return routes


def find_heavy_page_groups() -> list[str]:
    groups = []
    for name in ("orchestrator", "memory", "persona", "tools", "history", "capabilities"):
        if (REPO_ROOT / "apps/desktop/src/components" / name).exists():
            groups.append(name)
    return groups


def find_large_api_groups() -> list[str]:
    groups = []
    for name in ("orchestrator", "self_programming", "memory", "mcp", "capabilities", "world", "persona"):
        if (REPO_ROOT / "services/core/app" / name).exists():
            groups.append(name)
    return groups


def page_file_count() -> int:
    if not PAGES_DIR.exists():
        return 0
    return sum(1 for path in PAGES_DIR.glob("*.tsx") if path.is_file())


def analyze() -> dict[str, object]:
    app_routes = extract_app_routes()
    page_imports = extract_page_imports()
    api_routes = extract_api_routes()
    return {
        "repo_root": str(REPO_ROOT),
        "frontend": {
            "app_routes": app_routes,
            "route_count": len(app_routes),
            "page_imports": page_imports,
            "page_file_count": page_file_count(),
            "heavy_component_groups": find_heavy_page_groups(),
        },
        "backend": {
            "api_route_count": len(api_routes),
            "api_route_sample": api_routes[:30],
            "large_domain_groups": find_large_api_groups(),
        },
        "simplification_hints": [
            "Prefer removing or hiding routes before deleting their implementation.",
            "Cross-check heavy frontend groups against default routes before cutting them.",
            "Cross-check backend domain groups against current frontend usage before removing APIs.",
            "If an area is present in code but absent from the default route flow, it is a stronger simplification candidate.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
