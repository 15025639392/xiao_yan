from __future__ import annotations

from typing import Any


def format_browser_open_output(output: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {
        "session_id": output.get("session_id"),
        "url": output.get("url"),
        "resolved_url": output.get("resolved_url"),
        "title": output.get("title"),
        "status": output.get("status"),
        "opened_at": output.get("opened_at"),
        "capability_request_id": request_id,
    }


def format_browser_snapshot_output(output: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {
        "session_id": output.get("session_id"),
        "url": output.get("url"),
        "title": output.get("title"),
        "text_content": output.get("text_content"),
        "accessibility_tree": output.get("accessibility_tree"),
        "screenshot_path": output.get("screenshot_path"),
        "captured_at": output.get("captured_at"),
        "capability_request_id": request_id,
    }


def format_browser_extract_output(output: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {
        "session_id": output.get("session_id"),
        "target": output.get("target"),
        "content": output.get("content"),
        "structured_data": output.get("structured_data"),
        "source_url": output.get("source_url"),
        "captured_at": output.get("captured_at"),
        "capability_request_id": request_id,
    }


def format_browser_close_output(output: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {
        "session_id": output.get("session_id"),
        "closed_at": output.get("closed_at"),
        "status": output.get("status"),
        "capability_request_id": request_id,
    }


def merge_browser_open_with_snapshot(
    open_output: dict[str, Any],
    snapshot_output: dict[str, Any] | None,
    *,
    request_id: str,
) -> dict[str, Any]:
    merged = format_browser_open_output(open_output, request_id=request_id)
    if not isinstance(snapshot_output, dict):
        return merged

    merged["text_content"] = snapshot_output.get("text_content", "")
    merged["title"] = snapshot_output.get("title") or merged.get("title") or ""
    merged["links"] = extract_links_from_accessibility_tree(snapshot_output.get("accessibility_tree"))
    merged["screenshot_path"] = snapshot_output.get("screenshot_path")
    merged["captured_at"] = snapshot_output.get("captured_at")
    return merged


def extract_links_from_accessibility_tree(tree: Any) -> list[dict[str, str]]:
    if not isinstance(tree, list):
        return []
    links: list[dict[str, str]] = []
    for node in tree:
        if not isinstance(node, dict):
            continue
        role = node.get("role", "")
        if role == "link":
            name = node.get("name") or ""
            url = node.get("url") or ""
            if name and url:
                links.append({"text": name, "url": url})
        elif isinstance(node.get("children"), list):
            links.extend(extract_links_from_accessibility_tree(node["children"]))
    return links
