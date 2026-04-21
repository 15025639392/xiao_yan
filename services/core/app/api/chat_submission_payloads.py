from __future__ import annotations

from app.api.chat_runtime_helpers import merge_chat_stream_content


CHAT_FILE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a file and return its content. Use absolute paths when possible.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2 * 1024 * 1024},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_directory",
        "description": "List files and directories under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
                "pattern": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_files",
        "description": "Search text in files under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "search_path": {"type": "string"},
                "file_pattern": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Write UTF-8 text to a file path. Requires full_access for granted folders.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "create_dirs": {"type": "boolean"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
]

CHAT_BROWSER_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "browser_open",
        "description": "Open a URL in a browser and return the page metadata, text content, and links. Use this when you need to access external websites or web content. This is the only browser tool you need — it returns everything in one call.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to open"},
                "session_id": {"type": "string", "description": "Optional session ID to reuse an existing browser session"},
                "headless": {"type": "boolean", "description": "Run browser in headless mode (default: true)"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_snapshot",
        "description": "Get a snapshot of the current browser page content. Usually not needed since browser_open already returns page content.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
                "include_text": {"type": "boolean", "description": "Include text content (default: true)"},
                "max_text_bytes": {"type": "integer", "description": "Max text bytes to return"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_extract",
        "description": "Extract structured content from the current browser page using a CSS selector or text target.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
                "target": {"type": "string", "description": "CSS selector or text pattern to extract"},
                "schema": {"type": "object", "description": "Optional schema for structured extraction"},
                "max_items": {"type": "integer", "description": "Max items to extract"},
            },
            "required": ["session_id", "target"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_fill_form",
        "description": "Fill form fields (title and body) in a browser session that already has the publish page open. Use after browser_open opened the publish page.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
                "title": {"type": "string", "description": "Title text to fill into the title field"},
                "body": {"type": "string", "description": "Body/description text to fill into the body field"},
            },
            "required": ["session_id", "title", "body"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_click_element",
        "description": "Click a UI element in a browser session using a CSS selector. Use after browser_open and browser_fill_form to submit or confirm a form.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
                "selector": {"type": "string", "description": "CSS selector for the element to click (e.g., 'button[type=\"submit\"]', '#publish-btn')"},
            },
            "required": ["session_id", "selector"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_publish",
        "description": "Fill form fields and click the publish button in a single operation. Use after browser_open opened the Xiaohongshu publish page. This is the main auto-publish capability for Xiaohongshu.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
                "title": {"type": "string", "description": "Title text to fill into the title field"},
                "body": {"type": "string", "description": "Body/description text to fill into the body field"},
                "publish_selector": {"type": "string", "description": "CSS selector for the publish button (e.g., 'button[type=\"submit\"]')"},
            },
            "required": ["session_id", "title", "body", "publish_selector"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_find_publish_button",
        "description": "Find the publish button on the current page. Tries multiple selector strategies and returns the first visible one found. Use after browser_open opened the Xiaohongshu publish page to discover the correct publish button selector.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "browser_close",
        "description": "Close a browser session.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID from browser_open"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
]


def build_resume_instruction(partial_content: str) -> str:
    return (
        "这是一次失败后的继续生成。"
        "你必须紧接着下面这段 assistant 已输出内容继续生成，"
        "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
        f"已输出内容：\n{partial_content}"
    )


def resolve_completed_output_text(
    *,
    current_output_text: str,
    completed_output_text: str,
    initial_output_text: str,
) -> str:
    if not completed_output_text:
        return current_output_text
    if initial_output_text:
        return merge_chat_stream_content(initial_output_text, completed_output_text)
    if completed_output_text != current_output_text:
        return completed_output_text
    return current_output_text
