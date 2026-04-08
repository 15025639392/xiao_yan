from __future__ import annotations

FILE_POLICY_VERSION = "2026-04-08-v1"

DEFAULT_MAX_READ_BYTES = 512 * 1024
DEFAULT_MAX_WRITE_BYTES = 512 * 1024
DEFAULT_MAX_SEARCH_RESULTS = 200
DEFAULT_MAX_LIST_ENTRIES = 500

DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS: tuple[str, ...] = (
    "*.py",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.json",
    "*.md",
    "*.txt",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.rs",
    "*.go",
    "*.java",
    "*.c",
    "*.cpp",
    "*.h",
    "*.hpp",
    "*.css",
    "*.html",
)

FILE_MAX_READ_BYTES_BOUNDS = (1, 2 * 1024 * 1024)
FILE_MAX_WRITE_BYTES_BOUNDS = (1, 2 * 1024 * 1024)
FILE_MAX_SEARCH_RESULTS_BOUNDS = (1, 500)
FILE_MAX_LIST_ENTRIES_BOUNDS = (1, 2000)

_ALLOWED_SEARCH_PATTERNS_SET = set(DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS)


def _normalize_bounded_int(value: int | None, *, default: int, bounds: tuple[int, int], field_name: str) -> int:
    if value is None:
        return default
    low, high = bounds
    next_value = int(value)
    if next_value < low or next_value > high:
        raise ValueError(f"{field_name} must be between {low} and {high}")
    return next_value


def _normalize_search_patterns(value: list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return list(DEFAULT_ALLOWED_SEARCH_FILE_PATTERNS)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in value:
        pattern = raw.strip()
        if not pattern:
            continue
        if pattern in seen:
            continue
        if pattern not in _ALLOWED_SEARCH_PATTERNS_SET:
            raise ValueError(f"allowed_search_file_patterns contains unsupported value: {pattern}")
        seen.add(pattern)
        normalized.append(pattern)
    if not normalized:
        raise ValueError("allowed_search_file_patterns must not be empty")
    return normalized


def normalize_file_policy_values(
    *,
    max_read_bytes: int | None = None,
    max_write_bytes: int | None = None,
    max_search_results: int | None = None,
    max_list_entries: int | None = None,
    allowed_search_file_patterns: list[str] | tuple[str, ...] | None = None,
) -> tuple[int, int, int, int, list[str]]:
    read_bytes = _normalize_bounded_int(
        max_read_bytes,
        default=DEFAULT_MAX_READ_BYTES,
        bounds=FILE_MAX_READ_BYTES_BOUNDS,
        field_name="max_read_bytes",
    )
    write_bytes = _normalize_bounded_int(
        max_write_bytes,
        default=DEFAULT_MAX_WRITE_BYTES,
        bounds=FILE_MAX_WRITE_BYTES_BOUNDS,
        field_name="max_write_bytes",
    )
    search_results = _normalize_bounded_int(
        max_search_results,
        default=DEFAULT_MAX_SEARCH_RESULTS,
        bounds=FILE_MAX_SEARCH_RESULTS_BOUNDS,
        field_name="max_search_results",
    )
    list_entries = _normalize_bounded_int(
        max_list_entries,
        default=DEFAULT_MAX_LIST_ENTRIES,
        bounds=FILE_MAX_LIST_ENTRIES_BOUNDS,
        field_name="max_list_entries",
    )
    patterns = _normalize_search_patterns(allowed_search_file_patterns)
    return read_bytes, write_bytes, search_results, list_entries, patterns


def build_file_policy_payload(
    *,
    max_read_bytes: int | None = None,
    max_write_bytes: int | None = None,
    max_search_results: int | None = None,
    max_list_entries: int | None = None,
    allowed_search_file_patterns: list[str] | tuple[str, ...] | None = None,
    revision: int | None = None,
) -> dict:
    read_bytes, write_bytes, search_results, list_entries, patterns = normalize_file_policy_values(
        max_read_bytes=max_read_bytes,
        max_write_bytes=max_write_bytes,
        max_search_results=max_search_results,
        max_list_entries=max_list_entries,
        allowed_search_file_patterns=allowed_search_file_patterns,
    )
    payload = {
        "version": FILE_POLICY_VERSION,
        "max_read_bytes": read_bytes,
        "max_write_bytes": write_bytes,
        "max_search_results": search_results,
        "max_list_entries": list_entries,
        "allowed_search_file_patterns": patterns,
    }
    if revision is not None:
        payload["revision"] = int(revision)
    return payload
