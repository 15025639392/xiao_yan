#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
from collections import defaultdict, deque
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "apps/desktop/src"
APP_TSX = SRC_ROOT / "App.tsx"
API_MAPPING_SCRIPT = Path(__file__).with_name("analyze_api_mapping.py")

IMPORT_STATEMENT_PATTERN = re.compile(
    r'import\s+(?P<is_type>type\s+)?(?P<imports>[\s\S]*?)\s+from\s+"(?P<source>[^"]+)";',
    re.M,
)
ROUTE_COMPONENT_PATTERN = re.compile(
    r'route === "(?P<route>[a-z_]+)"\s*\?\s*\([\s\S]{0,400}?<(?P<component>[A-Z][A-Za-z0-9]+)',
    re.M,
)
DEFAULT_COMPONENT_PATTERN = re.compile(r'\)\s*:\s*\(\s*<(?P<component>[A-Z][A-Za-z0-9]+)', re.M)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def resolve_local_import(importer: Path, source: str) -> Path | None:
    base = (importer.parent / source).resolve()
    candidates = [
        base,
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base / "index.ts",
        base / "index.tsx",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def parse_import_statements(path: Path) -> list[dict[str, object]]:
    content = read_text(path)
    parsed: list[dict[str, object]] = []
    for match in IMPORT_STATEMENT_PATTERN.finditer(content):
        is_type_only = bool(match.group("is_type"))
        imports = match.group("imports").strip()
        source = match.group("source").strip()
        names: list[str] = []
        if imports.startswith("{"):
            inner = imports.strip("{} \n")
            for raw in inner.split(","):
                name = raw.strip()
                if not name or name.startswith("type "):
                    continue
                if " as " in name:
                    name = name.split(" as ", 1)[0].strip()
                names.append(name)
        elif "," in imports:
            default_part, _, remainder = imports.partition(",")
            default_name = default_part.strip()
            if default_name and not default_name.startswith("type "):
                names.append(default_name)
            remainder = remainder.strip()
            if remainder.startswith("{"):
                inner = remainder.strip("{} \n")
                for raw in inner.split(","):
                    name = raw.strip()
                    if not name or name.startswith("type "):
                        continue
                    if " as " in name:
                        name = name.split(" as ", 1)[0].strip()
                    names.append(name)
        else:
            default_name = imports.strip()
            if default_name and not default_name.startswith("type "):
                names.append(default_name)
        parsed.append({"source": source, "names": names, "is_type_only": is_type_only})
    return parsed


def list_frontend_files() -> list[Path]:
    return sorted(
        path
        for path in SRC_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".ts", ".tsx"}
    )


def build_import_graph() -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, str]]:
    graph: dict[str, list[str]] = defaultdict(list)
    direct_api_imports: dict[str, list[str]] = defaultdict(list)
    app_import_symbols: dict[str, str] = {}

    for path in list_frontend_files():
        relative = normalize_rel(path)
        for item in parse_import_statements(path):
            source = str(item["source"])
            names = [str(name) for name in item["names"]]
            if source.endswith("/lib/api") or source == "./lib/api" or source == "../lib/api":
                if names and not bool(item["is_type_only"]):
                    direct_api_imports[relative].extend(names)
                continue
            if not source.startswith("."):
                continue
            resolved = resolve_local_import(path, source)
            if resolved is None or not str(resolved).startswith(str(SRC_ROOT)):
                continue
            target = normalize_rel(resolved)
            graph[relative].append(target)
            if path == APP_TSX:
                for name in names:
                    app_import_symbols[name] = target

    normalized_api_imports = {
        key: sorted(set(value))
        for key, value in direct_api_imports.items()
    }
    normalized_graph = {
        key: sorted(set(value))
        for key, value in graph.items()
    }
    return normalized_graph, normalized_api_imports, app_import_symbols


def extract_route_components(app_import_symbols: dict[str, str]) -> list[dict[str, str]]:
    content = read_text(APP_TSX)
    entries: list[dict[str, str]] = []
    for route, component in ROUTE_COMPONENT_PATTERN.findall(content):
        file_path = app_import_symbols.get(component)
        if file_path is None:
            continue
        entries.append({"route": route, "component": component, "file": file_path})

    default_match = DEFAULT_COMPONENT_PATTERN.search(content)
    if default_match:
        component = default_match.group("component")
        file_path = app_import_symbols.get(component)
        if file_path is not None:
            entries.append({"route": "overview", "component": component, "file": file_path})

    deduped: dict[str, dict[str, str]] = {}
    for entry in entries:
        deduped[entry["route"]] = entry
    return [deduped[key] for key in sorted(deduped)]


def walk_reachable(start: str, graph: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for next_item in graph.get(current, []):
            if next_item not in visited:
                queue.append(next_item)
    return sorted(visited)


def load_api_mapping_module():
    spec = importlib.util.spec_from_file_location("analyze_api_mapping_module", API_MAPPING_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load analyze_api_mapping.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify_route_flow(
    api_function_count: int,
    backend_route_count: int,
    unmapped_api_functions: list[str],
    unmatched_call_details: list[dict[str, object]],
) -> dict[str, object]:
    anomalies: list[dict[str, object]] = []
    recommendations: list[str] = []
    suggested_actions: list[dict[str, object]] = []
    decision_cards: list[dict[str, object]] = []

    if unmatched_call_details:
        grouped_functions: dict[tuple[str, str], list[str]] = defaultdict(list)
        grouped_details: dict[tuple[str, str], dict[str, object]] = {}
        grouped_actions: dict[tuple[str, str], dict[str, object]] = {}
        grouped_decisions: dict[tuple[str, str], dict[str, object]] = {}
        for item in unmatched_call_details:
            anomaly_key = (str(item["anomaly_type"]), str(item["severity"]))
            grouped_functions[anomaly_key].append(str(item["function"]))
            grouped_details.setdefault(anomaly_key, item)
            action_key = (str(item["default_action"]), str(item["default_action_priority"]))
            action_group = grouped_actions.setdefault(
                action_key,
                {
                    "action": action_key[0],
                    "priority": action_key[1],
                    "summary": str(item["default_action_summary"]),
                    "functions": [],
                    "source_anomaly_types": set(),
                },
            )
            action_group["functions"].append(str(item["function"]))
            action_group["source_anomaly_types"].add(str(item["anomaly_type"]))
            decision = item["decision_card"]
            decision_key = (str(decision["decision"]), str(decision["priority"]))
            decision_group = grouped_decisions.setdefault(
                decision_key,
                {
                    "decision": str(decision["decision"]),
                    "priority": str(decision["priority"]),
                    "title": str(decision["title"]),
                    "summary": str(decision["summary"]),
                    "rationale": str(decision["rationale"]),
                    "execution_mode_hint": str(decision["execution_mode_hint"]),
                    "functions": [],
                    "source_anomaly_types": set(),
                },
            )
            decision_group["functions"].append(str(item["function"]))
            decision_group["source_anomaly_types"].add(str(item["anomaly_type"]))

        for anomaly_key, functions in sorted(grouped_functions.items()):
            detail = grouped_details[anomaly_key]
            anomalies.append(
                {
                    "type": anomaly_key[0],
                    "severity": anomaly_key[1],
                    "functions": sorted(functions),
                    "reason": detail["reason"],
                    "recommended_action": detail["recommended_action"],
                    "backend_code_hint_sample": detail.get("backend_code_hint_sample", []),
                    "same_domain_route_sample": detail.get("same_domain_route_sample", []),
                }
            )
        for action_key, detail in sorted(grouped_actions.items()):
            suggested_actions.append(
                {
                    "action": action_key[0],
                    "priority": action_key[1],
                    "summary": detail["summary"],
                    "functions": sorted(set(detail["functions"])),
                    "source_anomaly_types": sorted(detail["source_anomaly_types"]),
                }
            )
        for decision_key, detail in sorted(grouped_decisions.items()):
            decision_cards.append(
                {
                    "decision": decision_key[0],
                    "priority": decision_key[1],
                    "title": detail["title"],
                    "summary": detail["summary"],
                    "rationale": detail["rationale"],
                    "execution_mode_hint": detail["execution_mode_hint"],
                    "functions": sorted(set(detail["functions"])),
                    "source_anomaly_types": sorted(detail["source_anomaly_types"]),
                }
            )
        recommendations.append(
            "Resolve route-level anomaly findings before treating this route as a safe deletion or freeze candidate."
        )

    if api_function_count == 0 and backend_route_count == 0:
        recommendations.append(
            "This route currently looks UI-only from the import graph; verify runtime usage before deleting it."
        )
    elif api_function_count > 0 and not unmapped_api_functions:
        recommendations.append(
            "The UI/API/backend chain is structurally mapped; you can review this route for thinning or removal with lower API uncertainty."
        )

    decision_names = {item["decision"] for item in decision_cards}
    execution_hints = {item["execution_mode_hint"] for item in decision_cards}
    safety_gates = [
        {
            "gate": "blocking_anomalies_resolved",
            "passed": not anomalies,
            "reason": (
                "No blocking anomalies remain."
                if not anomalies
                else "Route still contains blocking anomalies; do not treat it as a direct deletion candidate."
            ),
        },
        {
            "gate": "single_decision_path",
            "passed": len(decision_names) <= 1,
            "reason": (
                "A single dominant decision path exists."
                if len(decision_names) <= 1
                else "Multiple conflicting decision paths exist; keep this in decision-only mode."
            ),
        },
        {
            "gate": "guided_execution_possible",
            "passed": bool(decision_cards) and len(execution_hints) == 1 and "decision_only" not in execution_hints,
            "reason": (
                "All decision cards point to the same guided execution direction."
                if bool(decision_cards) and len(execution_hints) == 1 and "decision_only" not in execution_hints
                else "Guided execution is not safe yet; stay in decision-only mode."
            ),
        },
    ]

    execution_mode = "decision_only"
    if decision_cards and safety_gates[0]["passed"] and safety_gates[1]["passed"] and safety_gates[2]["passed"]:
        execution_mode = next(iter(execution_hints))
    elif not decision_cards and not anomalies:
        execution_mode = "eligible_for_safe_cleanup"

    return {
        "status": "needs_review" if anomalies else "ok",
        "deletion_readiness": "blocked" if anomalies else "reviewable",
        "anomalies": anomalies,
        "suggested_actions": suggested_actions,
        "decision_cards": decision_cards,
        "safety_gates": safety_gates,
        "execution_mode": execution_mode,
        "recommendations": recommendations,
    }


def analyze() -> dict[str, object]:
    graph, direct_api_imports, app_import_symbols = build_import_graph()
    route_components = extract_route_components(app_import_symbols)
    api_mapping_module = load_api_mapping_module()
    api_mapping_payload = api_mapping_module.analyze()
    frontend_api_function_names = {
        item["function"]
        for item in api_mapping_module.extract_frontend_calls()
        if isinstance(item, dict) and "function" in item
    }
    mapped_by_function = {
        item["function"]: item
        for item in api_mapping_payload.get("mapped_frontend_calls", [])
        if isinstance(item, dict) and "function" in item
    }
    unmatched_by_function = {
        item["function"]: item
        for item in api_mapping_payload.get("unmatched_frontend_calls", [])
        if isinstance(item, dict) and "function" in item
    }

    route_flows: list[dict[str, object]] = []
    for entry in route_components:
        reachable_files = walk_reachable(entry["file"], graph)
        api_functions: list[str] = []
        for file_path in reachable_files:
            api_functions.extend(direct_api_imports.get(file_path, []))
        api_functions = sorted({name for name in api_functions if name in frontend_api_function_names})
        backend_routes = sorted(
            {
                f'{item["method"]} {item["path"]}'
                for function_name in api_functions
                for item in [mapped_by_function.get(function_name)]
                if item is not None
            }
        )
        unmapped_api_functions = sorted(
            function_name for function_name in api_functions if function_name not in mapped_by_function
        )
        unmatched_call_details = [
            unmatched_by_function[function_name]
            for function_name in unmapped_api_functions
            if function_name in unmatched_by_function
        ]
        classification = classify_route_flow(
            api_function_count=len(api_functions),
            backend_route_count=len(backend_routes),
            unmapped_api_functions=unmapped_api_functions,
            unmatched_call_details=unmatched_call_details,
        )
        route_flows.append(
            {
                "route": entry["route"],
                "root_component": entry["component"],
                "root_file": entry["file"],
                "reachable_files_count": len(reachable_files),
                "reachable_files_sample": reachable_files[:20],
                "api_functions": api_functions,
                "api_function_count": len(api_functions),
                "backend_routes": backend_routes,
                "backend_route_count": len(backend_routes),
                "unmapped_api_functions": unmapped_api_functions,
                "unmatched_call_details": unmatched_call_details,
                "status": classification["status"],
                "deletion_readiness": classification["deletion_readiness"],
                "anomalies": classification["anomalies"],
                "suggested_actions": classification["suggested_actions"],
                "decision_cards": classification["decision_cards"],
                "safety_gates": classification["safety_gates"],
                "execution_mode": classification["execution_mode"],
                "recommendations": classification["recommendations"],
            }
        )

    anomaly_routes = [
        {
            "route": item["route"],
            "root_component": item["root_component"],
            "unmapped_api_functions": item["unmapped_api_functions"],
            "anomaly_types": [anomaly["type"] for anomaly in item["anomalies"]],
            "deletion_readiness": item["deletion_readiness"],
            "recommended_actions": [anomaly["recommended_action"] for anomaly in item["anomalies"]],
            "suggested_actions": item["suggested_actions"],
            "decision_cards": item["decision_cards"],
            "execution_mode": item["execution_mode"],
        }
        for item in route_flows
        if item["anomalies"]
    ]

    return {
        "repo_root": str(REPO_ROOT),
        "summary": {
            "routes_analyzed": len(route_flows),
            "routes_with_api_usage": sum(1 for item in route_flows if item["api_function_count"] > 0),
            "routes_with_unmapped_api_functions": sum(1 for item in route_flows if item["unmapped_api_functions"]),
            "routes_with_anomalies": len(anomaly_routes),
            "routes_blocked_from_deletion": sum(
                1 for item in route_flows if item["deletion_readiness"] == "blocked"
            ),
            "total_unmapped_api_functions": sum(len(item["unmapped_api_functions"]) for item in route_flows),
            "routes_with_suggested_actions": sum(1 for item in route_flows if item["suggested_actions"]),
            "routes_with_decision_cards": sum(1 for item in route_flows if item["decision_cards"]),
            "routes_in_guided_execution_mode": sum(
                1 for item in route_flows if item["execution_mode"] in {"guided_backend_patch", "guided_frontend_patch"}
            ),
        },
        "route_flows": route_flows,
        "review_candidates": anomaly_routes,
        "interpretation": [
            "Use this view before removing a route, page, or top-level component.",
            "If a route reaches many files but few backend routes, it may be mostly presentational and easier to simplify.",
            "If a route reaches many API functions and backend routes, prefer hiding or thinning it before removing it.",
            "Unmapped API functions under a route are stronger review candidates because they may indicate stale UI logic or incomplete backend support.",
            "Routes marked as blocked should not be deleted until the anomaly is resolved or explicitly documented as accepted risk.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
