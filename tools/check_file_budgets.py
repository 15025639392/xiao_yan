#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
SKIP_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
}


@dataclass(frozen=True)
class Budget:
    label: str
    warn: int
    fail: int


BUDGETS = [
    (
        lambda path: path.suffix == ".py"
        and "tests" not in path.parts
        and "scripts" not in path.parts,
        Budget("backend business file", warn=500, fail=800),
    ),
    (
        lambda path: path.suffix in {".ts", ".tsx", ".js", ".jsx"}
        and (
            "pages" in path.parts
            or "components" in path.parts
            or path.name in {"App.tsx", "App.ts", "App.jsx", "App.js"}
        ),
        Budget("frontend page/component", warn=400, fail=600),
    ),
    (
        lambda path: path.suffix in {".ts", ".tsx", ".js", ".jsx"},
        Budget("frontend/supporting module", warn=500, fail=800),
    ),
]


def should_skip(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return True
    name = path.name
    if "tests" in path.parts:
        return True
    if name.startswith("test_"):
        return True
    if any(token in name for token in (".test.", ".spec.")):
        return True
    return False


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def budget_for(path: Path) -> Budget | None:
    for predicate, budget in BUDGETS:
        if predicate(path):
            return budget
    return None


def collect_candidates(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in DEFAULT_EXTENSIONS
        and not should_skip(path)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check source-file size budgets to keep AI changes from inflating single files."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to scan. Defaults to current directory.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional file paths to check. When omitted, scan the whole repository.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    warnings: list[tuple[Path, int, Budget]] = []
    failures: list[tuple[Path, int, Budget]] = []

    if args.files:
        candidates = []
        for raw_path in args.files:
            path = (root / raw_path).resolve()
            if not path.exists() or not path.is_file():
                continue
            if path.suffix not in DEFAULT_EXTENSIONS or should_skip(path):
                continue
            candidates.append(path)
        candidates = sorted(set(candidates))
    else:
        candidates = collect_candidates(root)

    for path in candidates:
        budget = budget_for(path)
        if budget is None:
            continue
        count = line_count(path)
        if count > budget.fail:
            failures.append((path, count, budget))
        elif count > budget.warn:
            warnings.append((path, count, budget))

    if not warnings and not failures:
        print("No source files exceed configured size budgets.")
        return 0

    if failures:
        print("Failing files:")
        for path, count, budget in failures:
            print(
                f"  FAIL {count:4d} lines  {path.relative_to(root)}"
                f"  ({budget.label}, fail>{budget.fail})"
            )

    if warnings:
        print("Warning files:")
        for path, count, budget in warnings:
            print(
                f"  WARN {count:4d} lines  {path.relative_to(root)}"
                f"  ({budget.label}, warn>{budget.warn})"
            )

    print(
        "\nTip: prefer extracting pure helpers, subcomponents, adapters, or repositories instead"
        " of adding more logic into an oversized file."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
