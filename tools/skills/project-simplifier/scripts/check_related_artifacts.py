#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SEARCH_ROOTS = [
    REPO_ROOT / "docs",
    REPO_ROOT / "services/core/tests",
    REPO_ROOT / "apps/desktop/src",
    REPO_ROOT / "tools/skills",
    REPO_ROOT / "README.md",
]
IGNORED_PARTS = {"node_modules", ".git", "__pycache__", ".venv", ".pytest_cache", ".npm-cache"}
GENERIC_BASENAMES = {"SKILL.md", "SOURCES.txt", "chroma.sqlite3", "README.md"}


def is_searchable(path: Path) -> bool:
    if any(part in IGNORED_PARTS for part in path.parts):
        return False
    if path.suffix.lower() not in {".md", ".py", ".ts", ".tsx"}:
        return False
    return path.is_file()


def iter_searchable_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.is_file():
            if is_searchable(root):
                files.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if is_searchable(path):
                files.append(path)
    return sorted(set(files))


def run_git_command(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def detect_changed_files() -> list[str]:
    tracked = run_git_command(["diff", "--name-only", "HEAD"])
    untracked = run_git_command(["ls-files", "--others", "--exclude-standard"])
    changed = sorted(set(tracked + untracked))
    return [path for path in changed if path and not path.startswith(".npm-cache/")]


def build_patterns(relative_path: str) -> list[tuple[str, str]]:
    path_obj = Path(relative_path)
    patterns: list[tuple[str, str]] = [(relative_path, "exact_path")]
    basename = path_obj.name
    if basename and basename != relative_path and basename not in GENERIC_BASENAMES:
        patterns.append((basename, "basename"))
    stem = path_obj.stem
    if stem and len(stem) >= 6 and basename not in GENERIC_BASENAMES:
        patterns.append((stem, "stem"))
    return patterns


def classify_artifact(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).as_posix()
    if relative.startswith("docs/") or relative == "README.md" or (
        relative.startswith("tools/skills/") and relative.endswith(".md")
    ):
        return "doc"
    if (
        relative.startswith("services/core/tests/")
        or "/tests/" in relative
        or relative.endswith(".test.tsx")
        or relative.endswith(".test.ts")
    ):
        return "test"
    return "code"


def find_references(changed_files: list[str]) -> dict[str, object]:
    searchable_files = iter_searchable_files()
    changed_set = set(changed_files)
    results: list[dict[str, object]] = []

    for changed in changed_files:
        matches: list[dict[str, str]] = []
        patterns = build_patterns(changed)
        for candidate in searchable_files:
            relative_candidate = candidate.relative_to(REPO_ROOT).as_posix()
            if relative_candidate == changed:
                continue
            content = candidate.read_text(encoding="utf-8", errors="replace")
            for pattern, reason in patterns:
                if pattern in content:
                    matches.append(
                        {
                            "artifact": relative_candidate,
                            "artifact_type": classify_artifact(candidate),
                            "matched_by": reason,
                            "changed_together": "yes" if relative_candidate in changed_set else "no",
                        }
                    )
                    break

        needs_review = [match for match in matches if match["changed_together"] == "no"]
        results.append(
            {
                "changed_file": changed,
                "matches": matches,
                "review_candidates": needs_review,
            }
        )

    summary = {
        "changed_files": len(changed_files),
        "files_with_related_artifacts": sum(1 for item in results if item["matches"]),
        "files_with_unupdated_related_artifacts": sum(1 for item in results if item["review_candidates"]),
    }
    return {"summary": summary, "items": results}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check docs/tests that may need updating after code changes.")
    parser.add_argument(
        "--changed-file",
        action="append",
        dest="changed_files",
        default=[],
        help="Changed file to inspect. Can be repeated. Defaults to current git diff + untracked files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed_files = args.changed_files or detect_changed_files()
    payload = find_references(changed_files)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
