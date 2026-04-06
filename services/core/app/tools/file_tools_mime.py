from __future__ import annotations

from pathlib import Path


_EXTENSION_MIME_TYPES = {
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".tsx": "text/typescript-jsx",
    ".jsx": "text/javascript-jsx",
    ".json": "application/json",
    ".md": "text/markdown",
    ".html": "text/html",
    ".css": "text/css",
    ".yaml": "text/yaml",
    ".yml": "text/yml",
    ".toml": "text/toml",
    ".xml": "text/xml",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".sh": "text/x-shellscript",
    ".sql": "text/x-sql",
    ".env": "text/x-env",
    ".lock": "text/x-json",
}


def guess_mime_type(path: Path) -> str:
    """简单猜测 MIME 类型（不依赖 python-magic）。"""
    return _EXTENSION_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


__all__ = [
    "guess_mime_type",
]
