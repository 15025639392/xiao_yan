#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_API_FILE = REPO_ROOT / "apps/desktop/src/lib/api.ts"
BACKEND_API_DIR = REPO_ROOT / "services/core/app/api"
BACKEND_APP_DIR = REPO_ROOT / "services/core/app"
BACKEND_TEST_DIR = REPO_ROOT / "services/core/tests"

EXPORT_FUNCTION_PATTERN = re.compile(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(")
BACKEND_ROUTE_PATTERN = re.compile(r'@router\.(get|post|put|delete|patch)\("([^"]+)"')
CALL_HELPER_PATTERN = re.compile(r'return\s+(get|post|put|del)<[^>]+>\((.+?)\);', re.S)
RAW_FETCH_PATTERN = re.compile(r'fetch\((.+?),\s*\{\s*method:\s*"([A-Z]+)"', re.S)
CAMEL_CASE_TOKEN_PATTERN = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_path(path: str) -> str:
    normalized = path.strip().strip('"').strip("'").strip("`")
    normalized = normalized.replace("${BASE_URL}", "")
    normalized = re.sub(r"\$\{[^}]+\}", "{param}", normalized)
    normalized = re.sub(r"\{[^}]+\}", "{param}", normalized)
    normalized = re.sub(r"(?<!/)\{param\}$", "", normalized)
    normalized = re.sub(r"/+", "/", normalized)
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    return normalized


def normalize_signature(method: str, path: str) -> str:
    return f"{method.upper()} {normalize_path(path)}"


def tokenize_text(value: str) -> list[str]:
    pieces = re.split(r"[^A-Za-z0-9]+", value)
    tokens: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        for match in CAMEL_CASE_TOKEN_PATTERN.findall(piece):
            token = match.lower()
            if token and token not in {"get", "post", "put", "delete", "fetch", "update"}:
                tokens.append(token)
    return tokens


def path_segments(path: str) -> list[str]:
    return [segment for segment in normalize_path(path).strip("/").split("/") if segment and segment != "{param}"]


def extract_exported_functions(content: str) -> list[tuple[str, str]]:
    functions: list[tuple[str, str]] = []
    matches = list(EXPORT_FUNCTION_PATTERN.finditer(content))
    for index, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        brace_start = content.find("{", start)
        if brace_start == -1:
            continue
        depth = 0
        end = None
        for offset in range(brace_start, len(content)):
            char = content[offset]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = offset
                    break
        if end is None:
            continue
        body = content[brace_start + 1 : end]
        functions.append((name, body))
    return functions


def extract_frontend_calls() -> list[dict[str, str]]:
    content = read_text(FRONTEND_API_FILE)
    calls: list[dict[str, str]] = []
    for function_name, body in extract_exported_functions(content):
        helper_match = CALL_HELPER_PATTERN.search(body)
        if helper_match:
            method, raw_args = helper_match.groups()
            path_match = re.search(r'([`"][^`"]*[/$A-Za-z0-9?{}_.:-][^`"]*[`"])', raw_args)
            if path_match:
                path_literal = path_match.group(1)
                calls.append(
                    {
                        "function": function_name,
                        "method": "DELETE" if method == "del" else method.upper(),
                        "path": normalize_path(path_literal),
                        "source": "helper",
                    }
                )
                continue

        raw_fetch_match = RAW_FETCH_PATTERN.search(body)
        if raw_fetch_match:
            raw_path, method = raw_fetch_match.groups()
            path_match = re.search(r'([`"][^`"]*[/$A-Za-z0-9?{}_.:-][^`"]*[`"])', raw_path)
            if path_match:
                calls.append(
                    {
                        "function": function_name,
                        "method": method.upper(),
                        "path": normalize_path(path_match.group(1)),
                        "source": "fetch",
                    }
                )
    return calls


def extract_backend_routes() -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    for path in sorted(BACKEND_API_DIR.glob("*_routes.py")):
        content = read_text(path)
        for method, route_path in BACKEND_ROUTE_PATTERN.findall(content):
            routes.append(
                {
                    "file": str(path.relative_to(REPO_ROOT)),
                    "method": method.upper(),
                    "path": normalize_path(route_path),
                }
            )
    return routes


def collect_code_hints(domain: str, tokens: set[str]) -> list[dict[str, str]]:
    hint_files: list[Path] = []
    domain_dir = BACKEND_APP_DIR / domain
    if domain_dir.exists():
        hint_files.extend(sorted(path for path in domain_dir.rglob("*.py") if path.is_file()))
    hint_files.extend(sorted(path for path in BACKEND_TEST_DIR.rglob("*.py") if path.is_file()))

    domain_tokens = {token.lower() for token in tokenize_text(domain)}
    if domain.endswith("s"):
        domain_tokens.add(domain[:-1].lower())
    signal_tokens = {token for token in tokens if token not in domain_tokens and token not in {"param"}}

    scored_hints: list[tuple[int, dict[str, str]]] = []
    for path in hint_files:
        text = read_text(path).lower()
        stem_tokens = set(tokenize_text(path.stem))
        matched_tokens = sorted(token for token in signal_tokens if token in text or token in stem_tokens)
        if not matched_tokens and not signal_tokens:
            matched_tokens = sorted(token for token in tokens if token in text or token in stem_tokens)
        if not matched_tokens:
            continue
        score = len(matched_tokens) * 10 + sum(5 for token in matched_tokens if token in stem_tokens)
        if path.parent == BACKEND_TEST_DIR:
            score -= 2
        scored_hints.append(
            (
                score,
                {
                    "file": str(path.relative_to(REPO_ROOT)),
                    "matched_tokens": matched_tokens[:8],
                },
            )
        )
    scored_hints.sort(key=lambda item: (-item[0], item[1]["file"]))
    return [item[1] for item in scored_hints[:8]]


def choose_backend_logic_subtype(
    evidence_tokens: set[str],
    code_hints: list[dict[str, str]],
) -> tuple[str, str, str]:
    hint_files = [str(item["file"]) for item in code_hints]
    hint_file_names = {Path(file).name for file in hint_files}
    execution_tokens = {"execution", "executions", "task", "tasks", "stats", "active", "progress", "scheduler"}

    if "decompose" in evidence_tokens and "decomposer.py" in hint_file_names:
        return (
            "decomposition_capability_without_api_route",
            "The frontend expects a decomposition capability, and backend decomposition logic exists, but no API route exposes it.",
            "Check whether the decomposition capability should be exposed as an API route or whether the frontend caller is obsolete.",
        )

    if evidence_tokens & execution_tokens and {"executor.py", "scheduler.py"} & hint_file_names:
        return (
            "execution_runtime_without_api_route",
            "The frontend expects execution-state or execution-stats data, and backend runtime logic exists, but no API route exposes it.",
            "Check whether execution runtime state should be surfaced through an API route or whether the frontend panel is reading an outdated contract.",
        )

    return (
        "backend_logic_without_api_route",
        "The frontend endpoint is unmatched, but the backend already has domain routes and code artifacts that suggest the capability exists below the API layer.",
        "Check whether an API route was never exposed, renamed, or partially removed before deleting the frontend caller.",
    )


def build_default_action(anomaly_type: str) -> dict[str, str]:
    if anomaly_type == "decomposition_capability_without_api_route":
        return {
            "action": "consider_adding_backend_api_route",
            "priority": "high",
            "summary": "Prefer reviewing whether the decomposition capability should be exposed to the current frontend workflow.",
        }
    if anomaly_type == "execution_runtime_without_api_route":
        return {
            "action": "consider_adding_backend_api_route",
            "priority": "high",
            "summary": "Prefer reviewing whether execution runtime data should be exposed through an API route for the current frontend panel.",
        }
    if anomaly_type == "backend_logic_without_api_route":
        return {
            "action": "investigate_api_surface_before_removal",
            "priority": "high",
            "summary": "Prefer checking API exposure gaps before removing the frontend caller.",
        }
    if anomaly_type == "frontend_contract_without_backend_route":
        return {
            "action": "decide_contract_owner_then_add_or_remove",
            "priority": "high",
            "summary": "Prefer deciding whether the contract should be implemented on the backend or removed from the frontend.",
        }
    if anomaly_type == "backend_code_hint_without_route":
        return {
            "action": "investigate_backend_signal_before_removal",
            "priority": "medium",
            "summary": "Prefer inspecting backend hints before removing the frontend caller.",
        }
    return {
        "action": "consider_removing_frontend_caller",
        "priority": "medium",
        "summary": "Prefer treating this as a stale frontend caller unless stronger backend evidence appears.",
    }


def build_decision_card(anomaly_type: str, call: dict[str, str]) -> dict[str, str]:
    function_name = call["function"]
    path = call["path"]

    if anomaly_type == "decomposition_capability_without_api_route":
        return {
            "decision": "suggest_add_backend_route",
            "priority": "high",
            "title": "建议补后端路由",
            "summary": f"`{function_name}` 指向 `{path}`，更像后端已有分解能力但未暴露 API。",
            "rationale": "Keep the frontend entry for now and review whether the decomposition capability should be exposed through an API route.",
            "execution_mode_hint": "guided_backend_patch",
        }
    if anomaly_type == "execution_runtime_without_api_route":
        return {
            "decision": "suggest_add_backend_route",
            "priority": "high",
            "title": "建议补后端路由",
            "summary": f"`{function_name}` 指向 `{path}`，更像执行态能力已存在但未暴露 API。",
            "rationale": "Keep the frontend panel for now and review whether execution runtime data should be exposed through an API route.",
            "execution_mode_hint": "guided_backend_patch",
        }
    if anomaly_type == "frontend_contract_without_backend_route":
        return {
            "decision": "suggest_decide_contract_owner",
            "priority": "high",
            "title": "建议先定契约归属",
            "summary": f"`{function_name}` 指向 `{path}`，前后端契约归属还不清晰。",
            "rationale": "Decide whether the backend should implement the contract or the frontend should remove it before making code changes.",
            "execution_mode_hint": "decision_only",
        }
    if anomaly_type == "backend_code_hint_without_route":
        return {
            "decision": "suggest_keep_observing",
            "priority": "medium",
            "title": "建议保留观察",
            "summary": f"`{function_name}` 指向 `{path}`，后端有零散信号但证据还不够强。",
            "rationale": "Inspect the hinted backend files before choosing between route exposure and frontend removal.",
            "execution_mode_hint": "decision_only",
        }
    if anomaly_type == "likely_stale_frontend_api":
        return {
            "decision": "suggest_remove_frontend_entry",
            "priority": "medium",
            "title": "建议删前端入口",
            "summary": f"`{function_name}` 指向 `{path}`，当前更像遗留前端契约。",
            "rationale": "Prefer removing or hiding the frontend caller unless product context requires keeping it.",
            "execution_mode_hint": "guided_frontend_patch",
        }
    return {
        "decision": "suggest_investigate_before_change",
        "priority": "high",
        "title": "建议先调查再改",
        "summary": f"`{function_name}` 指向 `{path}`，当前证据不足以直接补 API 或删前端。",
        "rationale": "Investigate the API surface and backend ownership before choosing a code change path.",
        "execution_mode_hint": "decision_only",
    }


def classify_unmatched_call(call: dict[str, str], backend_routes: list[dict[str, str]]) -> dict[str, object]:
    segments = path_segments(call["path"])
    domain = segments[0] if segments else ""
    prefix = "/" + "/".join(segments[:2]) if len(segments) >= 2 else (f"/{domain}" if domain else "")
    same_domain_routes = [
        route
        for route in backend_routes
        if domain and normalize_path(route["path"]).startswith(f"/{domain}")
    ]
    same_prefix_routes = [
        route
        for route in same_domain_routes
        if prefix and normalize_path(route["path"]).startswith(prefix)
    ]
    evidence_tokens = set(tokenize_text(call["function"])) | set(tokenize_text(call["path"]))
    code_hints = collect_code_hints(domain, evidence_tokens) if domain else []

    if code_hints and same_domain_routes:
        anomaly_type, reason, recommended_action = choose_backend_logic_subtype(evidence_tokens, code_hints)
        severity = "high"
    elif same_domain_routes:
        anomaly_type = "frontend_contract_without_backend_route"
        severity = "high"
        reason = (
            "The frontend endpoint sits under an active backend route family, but no matching backend route exists "
            "for this exact contract."
        )
        recommended_action = (
            "Verify whether the frontend contract is outdated or whether the backend route is still missing."
        )
    elif code_hints:
        anomaly_type = "backend_code_hint_without_route"
        severity = "medium"
        reason = (
            "No matching backend route was found, but backend source or tests contain related domain hints."
        )
        recommended_action = (
            "Inspect the hinted backend files before removing the frontend caller; implementation may exist outside "
            "the API layer."
        )
    else:
        anomaly_type = "likely_stale_frontend_api"
        severity = "medium"
        reason = (
            "Neither a matching backend route nor strong backend code hints were found for this frontend endpoint."
        )
        recommended_action = (
            "Treat this call as a likely stale frontend contract unless product or architecture context says otherwise."
        )

    default_action = build_default_action(anomaly_type)
    decision_card = build_decision_card(anomaly_type, call)

    return {
        "function": call["function"],
        "method": call["method"],
        "path": call["path"],
        "source": call["source"],
        "anomaly_type": anomaly_type,
        "severity": severity,
        "reason": reason,
        "recommended_action": recommended_action,
        "domain": domain or None,
        "same_domain_route_sample": same_domain_routes[:5],
        "same_prefix_route_sample": same_prefix_routes[:5],
        "backend_code_hint_sample": code_hints,
        "default_action": default_action["action"],
        "default_action_priority": default_action["priority"],
        "default_action_summary": default_action["summary"],
        "decision_card": decision_card,
    }


def analyze() -> dict[str, object]:
    frontend_calls = extract_frontend_calls()
    backend_routes = extract_backend_routes()
    backend_signatures = {
        normalize_signature(route["method"], route["path"]): route
        for route in backend_routes
    }

    mapped: list[dict[str, object]] = []
    unmatched_frontend: list[dict[str, object]] = []
    used_backend_signatures: set[str] = set()

    for call in frontend_calls:
        signature = normalize_signature(call["method"], call["path"])
        matched_route = backend_signatures.get(signature)
        if matched_route is None:
            unmatched_frontend.append(classify_unmatched_call(call, backend_routes))
            continue
        used_backend_signatures.add(signature)
        mapped.append(
            {
                "function": call["function"],
                "method": call["method"],
                "path": call["path"],
                "backend_file": matched_route["file"],
                "source": call["source"],
            }
        )

    unused_backend = [
        route
        for route in backend_routes
        if normalize_signature(route["method"], route["path"]) not in used_backend_signatures
    ]

    unmatched_by_type: dict[str, int] = {}
    unmatched_by_action: dict[str, int] = {}
    unmatched_by_decision: dict[str, int] = {}
    for item in unmatched_frontend:
        anomaly_type = str(item["anomaly_type"])
        unmatched_by_type[anomaly_type] = unmatched_by_type.get(anomaly_type, 0) + 1
        action_name = str(item["default_action"])
        unmatched_by_action[action_name] = unmatched_by_action.get(action_name, 0) + 1
        decision_name = str(item["decision_card"]["decision"])
        unmatched_by_decision[decision_name] = unmatched_by_decision.get(decision_name, 0) + 1

    return {
        "repo_root": str(REPO_ROOT),
        "summary": {
            "frontend_api_functions_mapped": len(mapped),
            "frontend_api_functions_unmatched": len(unmatched_frontend),
            "backend_routes_total": len(backend_routes),
            "backend_routes_without_frontend_mapping": len(unused_backend),
            "unmatched_frontend_by_type": unmatched_by_type,
            "unmatched_frontend_by_action": unmatched_by_action,
            "unmatched_frontend_by_decision": unmatched_by_decision,
        },
        "mapped_frontend_calls": mapped[:80],
        "unmatched_frontend_calls": unmatched_frontend[:80],
        "backend_routes_without_frontend_mapping_sample": unused_backend[:80],
        "interpretation": [
            "Unmatched frontend calls deserve a manual check before simplification because they may use raw fetch patterns or unsupported dynamic paths.",
            "Backend routes without frontend mapping are stronger simplification candidates, but still need product and default-flow review.",
            "Prefer hiding or removing frontend callers before deleting backend handlers.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
