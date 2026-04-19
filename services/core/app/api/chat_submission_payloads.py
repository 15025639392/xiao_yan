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
