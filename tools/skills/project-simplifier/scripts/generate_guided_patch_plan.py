#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_SRC_ROOT = REPO_ROOT / "apps/desktop/src"
UI_FLOW_SCRIPT = Path(__file__).with_name("analyze_ui_api_flow.py")
API_MAPPING_SCRIPT = Path(__file__).with_name("analyze_api_mapping.py")
ARTIFACT_SCRIPT = Path(__file__).with_name("check_related_artifacts.py")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_rel(path: str | Path) -> str:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj.relative_to(REPO_ROOT).as_posix()
    return path_obj.as_posix()


def load_module(script_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_code_files(root: Path, suffixes: set[str]) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes and "__pycache__" not in path.parts
    )


def find_symbol_references(symbol: str, root: Path, suffixes: set[str]) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    matches: list[str] = []
    for path in iter_code_files(root, suffixes):
        if pattern.search(read_text(path)):
            matches.append(normalize_rel(path))
    return matches


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def summarize_artifacts(
    artifact_module,
    candidate_change_files: list[str],
) -> dict[str, list[dict[str, object]]]:
    payload = artifact_module.find_references(candidate_change_files)
    candidate_set = set(candidate_change_files)
    buckets: dict[tuple[str, str], dict[str, dict[str, object]]] = {
        ("doc", "direct"): {},
        ("doc", "review"): {},
        ("test", "direct"): {},
        ("test", "review"): {},
    }

    for item in payload.get("items", []):
        changed_file = str(item["changed_file"])
        for match in item.get("matches", []):
            artifact = str(match["artifact"])
            if artifact in candidate_set:
                continue
            artifact_type = str(match["artifact_type"])
            if artifact_type not in {"doc", "test"}:
                continue
            matched_by = str(match["matched_by"])
            confidence = "direct" if matched_by in {"exact_path", "basename"} else "review"
            target_map = buckets[(artifact_type, confidence)]
            existing = target_map.setdefault(
                artifact,
                {
                    "file": artifact,
                    "matched_by": set(),
                    "related_to": set(),
                },
            )
            existing["matched_by"].add(matched_by)
            existing["related_to"].add(changed_file)

    def finalize(values: dict[str, dict[str, object]]) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for artifact, detail in values.items():
            items.append(
                {
                    "file": artifact,
                    "matched_by": sorted(detail["matched_by"]),
                    "related_to": sorted(detail["related_to"]),
                }
            )
        return sorted(items, key=lambda item: item["file"])

    return {
        "docs": finalize(buckets[("doc", "direct")]),
        "doc_manual_review": finalize(buckets[("doc", "review")]),
        "tests": finalize(buckets[("test", "direct")]),
        "test_manual_review": finalize(buckets[("test", "review")]),
    }


def build_backend_route_index(api_mapping_module) -> dict[str, str]:
    route_index: dict[str, str] = {}
    for route in api_mapping_module.extract_backend_routes():
        signature = f'{route["method"].upper()} {api_mapping_module.normalize_path(route["path"])}'
        route_index[signature] = str(route["file"])
    return route_index


def infer_patch_direction(route: dict[str, object]) -> str:
    current_mode = str(route["execution_mode"])
    if current_mode == "guided_backend_patch":
        return "backend_api_exposure"
    if current_mode == "guided_frontend_patch":
        return "frontend_cleanup"
    if current_mode == "eligible_for_safe_cleanup":
        return "safe_cleanup"

    decisions = {str(card["decision"]) for card in route.get("decision_cards", [])}
    if decisions == {"suggest_add_backend_route"}:
        return "backend_api_exposure"
    if decisions == {"suggest_remove_frontend_entry"}:
        return "frontend_cleanup"
    if decisions == {"suggest_keep_observing"}:
        return "observe_and_document"
    return "manual_decision"


def infer_next_execution_mode(route: dict[str, object]) -> str | None:
    hints = {str(card["execution_mode_hint"]) for card in route.get("decision_cards", [])}
    if len(hints) == 1:
        return next(iter(hints))
    return None


def infer_plan_status(route: dict[str, object]) -> str:
    current_mode = str(route["execution_mode"])
    if current_mode == "decision_only":
        return "plan_only"
    return "guided_patch_plan_available"


def collect_frontend_targets(route: dict[str, object], affected_functions: list[str]) -> tuple[list[str], list[str]]:
    references: list[str] = []
    for function_name in affected_functions:
        references.extend(find_symbol_references(function_name, FRONTEND_SRC_ROOT, {".ts", ".tsx"}))

    reference_files = unique(references)
    contract_files = [path for path in reference_files if path.endswith("/lib/api.ts")]
    caller_files = [path for path in reference_files if path not in contract_files]
    root_file = str(route["root_file"])
    if root_file not in caller_files:
        caller_files.insert(0, root_file)
    return unique(contract_files), unique(caller_files)


def collect_backend_targets(
    route: dict[str, object],
    backend_route_index: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    route_files: list[str] = []
    if not route.get("unmatched_call_details"):
        for signature in route.get("backend_routes", []):
            file_path = backend_route_index.get(str(signature))
            if file_path is not None:
                route_files.append(file_path)

    logic_files: list[str] = []
    test_files: list[str] = []
    for item in route.get("unmatched_call_details", []):
        for sample in item.get("same_domain_route_sample", []):
            route_files.append(str(sample["file"]))
        for sample in item.get("backend_code_hint_sample", []):
            file_path = str(sample["file"])
            if "/tests/" in file_path:
                test_files.append(file_path)
            else:
                logic_files.append(file_path)

    return unique(route_files), unique(logic_files), unique(test_files)


def build_steps(
    route: dict[str, object],
    patch_direction: str,
    plan_status: str,
    affected_functions: list[str],
    frontend_contract_files: list[str],
    frontend_caller_files: list[str],
    backend_route_files: list[str],
    backend_logic_files: list[str],
    doc_targets: list[dict[str, object]],
    test_targets: list[dict[str, object]],
    doc_review_targets: list[dict[str, object]],
    test_review_targets: list[dict[str, object]],
) -> list[str]:
    current_mode = str(route["execution_mode"])
    blocking_gates = [gate for gate in route.get("safety_gates", []) if not bool(gate["passed"])]
    steps: list[str] = []

    if plan_status == "plan_only":
        steps.append(
            f"当前执行模式仍是 `{current_mode}`，先停在整改计划与文档阶段，不直接自动落补丁。"
        )
        if blocking_gates:
            steps.append(
                "先处理未通过的门禁："
                + "；".join(f'`{gate["gate"]}` - {gate["reason"]}' for gate in blocking_gates)
            )

    if patch_direction == "backend_api_exposure":
        steps.extend(
            [
                "确认前端契约是否仍应保留，再决定由后端补 API 暴露而不是删前端入口。",
                (
                    "优先检查前端契约与调用点："
                    + ", ".join(f"`{item}`" for item in unique(frontend_contract_files + frontend_caller_files)[:6])
                ),
                (
                    "优先评估后端路由与实现落点："
                    + ", ".join(f"`{item}`" for item in unique(backend_route_files + backend_logic_files)[:6])
                ),
                f"补齐与 `{', '.join(affected_functions)}` 对应的 API 路由后，再回跑映射与三级流向分析。",
            ]
        )
    elif patch_direction == "frontend_cleanup":
        steps.extend(
            [
                "先确认这些前端契约确实已经废弃，再删除或隐藏入口，避免误删未暴露的真实能力。",
                (
                    "优先检查前端入口与调用点："
                    + ", ".join(f"`{item}`" for item in unique(frontend_contract_files + frontend_caller_files)[:6])
                ),
                "如果前端入口被删改，同步移除失效测试、说明文档和验证命令。",
            ]
        )
    elif patch_direction == "safe_cleanup":
        steps.extend(
            [
                "当前 route 没有阻断异常，可以进入低风险收敛计划，但仍需人工确认运行主链路不受影响。",
                (
                    "优先检查 route 根文件与直接后端落点："
                    + ", ".join(f"`{item}`" for item in unique(frontend_caller_files + backend_route_files)[:6])
                ),
                "如果最终删除入口或面板，同步更新导航、测试和文档，不保留失效引用。",
            ]
        )
    elif patch_direction == "observe_and_document":
        steps.extend(
            [
                "证据还不足以直接删前端或补后端，先保留能力并把异常结论、接受理由和后续 owner 写进文档。",
                "只允许做低风险探针式整理，不做会改变契约的补丁。",
            ]
        )
    else:
        steps.extend(
            [
                "当前更适合先定契约归属或补充证据，不直接进入自动整改。",
                "优先核对同域后端路由、后端代码线索和前端调用是否仍然匹配当前产品方向。",
            ]
        )

    if test_targets:
        steps.append(
            "同步处理测试："
            + ", ".join(f'`{item["file"]}`' for item in test_targets[:6])
        )
    if doc_targets:
        steps.append(
            "同步处理文档："
            + ", ".join(f'`{item["file"]}`' for item in doc_targets[:6])
        )
    if test_review_targets:
        steps.append(
            "额外人工复核测试："
            + ", ".join(f'`{item["file"]}`' for item in test_review_targets[:6])
        )
    if doc_review_targets:
        steps.append(
            "额外人工复核文档："
            + ", ".join(f'`{item["file"]}`' for item in doc_review_targets[:6])
        )
    steps.append(
        "收尾时运行 `analyze_api_mapping.py`、`analyze_ui_api_flow.py`、`check_related_artifacts.py` 和 `generate_change_doc.py`。"
    )
    return steps


def build_doc_suggestion(route_name: str, patch_direction: str) -> dict[str, str]:
    date_text = datetime.now().strftime("%Y-%m-%d")
    slug = f"{route_name}-{patch_direction.replace('_', '-')}"
    return {
        "slug": slug,
        "path": str(REPO_ROOT / "docs/plans" / f"{date_text}-{slug}-simplification.md"),
        "generate_command": (
            "python3 tools/skills/project-simplifier/scripts/generate_change_doc.py "
            f"--slug {slug}"
        ),
    }


def build_route_plan(
    route: dict[str, object],
    backend_route_index: dict[str, str],
    artifact_module,
) -> dict[str, object]:
    patch_direction = infer_patch_direction(route)
    plan_status = infer_plan_status(route)
    next_execution_mode = infer_next_execution_mode(route)
    affected_functions = (
        [str(item) for item in route.get("unmapped_api_functions", [])]
        or [str(item) for item in route.get("api_functions", [])]
    )
    frontend_contract_files, frontend_caller_files = collect_frontend_targets(route, affected_functions)
    backend_route_files, backend_logic_files, backend_test_hint_files = collect_backend_targets(
        route,
        backend_route_index,
    )

    candidate_change_files = unique(
        frontend_contract_files
        + frontend_caller_files
        + backend_route_files
        + backend_logic_files
        + backend_test_hint_files
    )
    artifact_seed_files = [path for path in candidate_change_files if Path(path).name not in {"__init__.py"}]
    artifact_summary = summarize_artifacts(artifact_module, artifact_seed_files or candidate_change_files)
    doc_targets = artifact_summary["docs"]
    doc_review_targets = artifact_summary["doc_manual_review"]
    test_targets = artifact_summary["tests"]
    test_review_targets = artifact_summary["test_manual_review"]

    existing_test_files = {item["file"] for item in test_targets}
    for file_path in backend_test_hint_files:
        if file_path not in existing_test_files:
            test_targets.append(
                {
                    "file": file_path,
                    "matched_by": ["backend_code_hint"],
                    "related_to": backend_logic_files[:1] or backend_route_files[:1] or [str(route["root_file"])],
                }
            )
    test_targets.sort(key=lambda item: item["file"])

    steps = build_steps(
        route=route,
        patch_direction=patch_direction,
        plan_status=plan_status,
        affected_functions=affected_functions,
        frontend_contract_files=frontend_contract_files,
        frontend_caller_files=frontend_caller_files,
        backend_route_files=backend_route_files,
        backend_logic_files=backend_logic_files,
        doc_targets=doc_targets,
        test_targets=test_targets,
        doc_review_targets=doc_review_targets,
        test_review_targets=test_review_targets,
    )

    return {
        "route": route["route"],
        "root_component": route["root_component"],
        "root_file": route["root_file"],
        "status": route["status"],
        "deletion_readiness": route["deletion_readiness"],
        "current_execution_mode": route["execution_mode"],
        "next_execution_mode_if_resolved": next_execution_mode,
        "plan_status": plan_status,
        "patch_direction": patch_direction,
        "auto_apply_patch": False,
        "affected_api_functions": affected_functions,
        "decision_cards": route.get("decision_cards", []),
        "suggested_actions": route.get("suggested_actions", []),
        "blocking_gates": [gate for gate in route.get("safety_gates", []) if not bool(gate["passed"])],
        "target_files": {
            "frontend_api_contract_files": frontend_contract_files,
            "frontend_caller_files": frontend_caller_files,
            "backend_route_files": backend_route_files,
            "backend_logic_files": backend_logic_files,
            "test_hint_files": backend_test_hint_files,
        },
        "sync_targets": {
            "docs": doc_targets,
            "tests": test_targets,
            "doc_manual_review": doc_review_targets,
            "test_manual_review": test_review_targets,
            "must_update_in_same_change": True,
        },
        "steps": steps,
        "doc_suggestion": build_doc_suggestion(str(route["route"]), patch_direction),
        "validation_commands": [
            "python3 tools/skills/project-simplifier/scripts/analyze_api_mapping.py",
            "python3 tools/skills/project-simplifier/scripts/analyze_ui_api_flow.py",
            (
                "python3 tools/skills/project-simplifier/scripts/generate_guided_patch_plan.py "
                f"--route {route['route']}"
            ),
            "python3 tools/skills/project-simplifier/scripts/check_related_artifacts.py",
        ],
    }


def select_routes(payload: dict[str, object], route_names: list[str], include_all_actionable: bool) -> list[dict[str, object]]:
    route_flows = payload.get("route_flows", [])
    route_by_name = {str(item["route"]): item for item in route_flows}

    if route_names:
        missing = [name for name in route_names if name not in route_by_name]
        if missing:
            raise SystemExit(f"Unknown route(s): {', '.join(missing)}")
        return [route_by_name[name] for name in route_names]

    if include_all_actionable:
        return [
            item
            for item in route_flows
            if item.get("decision_cards")
            or item.get("anomalies")
            or str(item.get("execution_mode")) != "decision_only"
        ]

    review_candidates = payload.get("review_candidates", [])
    selected = [route_by_name[str(item["route"])] for item in review_candidates if str(item["route"]) in route_by_name]
    if selected:
        return selected

    return [
        item
        for item in route_flows
        if item.get("decision_cards")
        or item.get("anomalies")
        or str(item.get("execution_mode")) != "decision_only"
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a guided patch workflow plan from UI/API/backend simplification analysis.",
    )
    parser.add_argument(
        "--route",
        action="append",
        dest="routes",
        default=[],
        help="Specific route to plan. Can be repeated. Defaults to review candidates only.",
    )
    parser.add_argument(
        "--all-actionable",
        action="store_true",
        help="Include all routes with anomalies, decision cards, or non-decision execution modes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ui_flow_module = load_module(UI_FLOW_SCRIPT, "project_simplifier_ui_flow")
    api_mapping_module = load_module(API_MAPPING_SCRIPT, "project_simplifier_api_mapping")
    artifact_module = load_module(ARTIFACT_SCRIPT, "project_simplifier_artifacts")

    ui_flow_payload = ui_flow_module.analyze()
    backend_route_index = build_backend_route_index(api_mapping_module)
    selected_routes = select_routes(ui_flow_payload, args.routes, args.all_actionable)
    plans = [build_route_plan(route, backend_route_index, artifact_module) for route in selected_routes]

    payload = {
        "repo_root": str(REPO_ROOT),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "routes_selected": len(plans),
            "routes_in_plan_only_mode": sum(1 for item in plans if item["plan_status"] == "plan_only"),
            "routes_ready_for_guided_patch_plan": sum(
                1 for item in plans if item["plan_status"] == "guided_patch_plan_available"
            ),
            "backend_direction_routes": sum(1 for item in plans if item["patch_direction"] == "backend_api_exposure"),
            "frontend_direction_routes": sum(1 for item in plans if item["patch_direction"] == "frontend_cleanup"),
            "safe_cleanup_routes": sum(1 for item in plans if item["patch_direction"] == "safe_cleanup"),
        },
        "plans": plans,
        "policy": [
            "This script only generates remediation plans. It does not emit or apply code patches.",
            "If current_execution_mode is decision_only, keep the result at plan/document level until blocking gates are resolved.",
            "If a plan changes code, docs and tests listed under sync_targets must be updated in the same change.",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
