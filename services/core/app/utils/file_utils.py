from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text_file(path: Path, *, encoding: str = "utf-8") -> str:
    return path.read_text(encoding=encoding)


def write_text_file(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    create_parent: bool = False,
) -> None:
    if create_parent:
        ensure_parent_dir(path)
    path.write_text(content, encoding=encoding)


def read_json_file(path: Path, *, encoding: str = "utf-8") -> Any:
    return json.loads(read_text_file(path, encoding=encoding))


def write_json_file(
    path: Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
    indent: int | None = None,
    create_parent: bool = False,
) -> None:
    serialized = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent)
    write_text_file(path, serialized, encoding=encoding, create_parent=create_parent)


__all__ = [
    "ensure_parent_dir",
    "read_text_file",
    "write_text_file",
    "read_json_file",
    "write_json_file",
]
