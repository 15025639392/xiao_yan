#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Deserialize;
use std::{
    collections::{BTreeSet, HashSet},
    fs,
    io::Read,
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    sync::Mutex,
    thread::JoinHandle,
    time::{Duration, Instant},
};
use tauri::{Emitter, Manager};

#[derive(Default)]
struct FsAccessState {
    allowed_dir: Option<PathBuf>,
    allowed_dir_canonical: Option<PathBuf>,
}

type SharedFsAccessState = Mutex<FsAccessState>;

#[derive(serde::Serialize)]
struct AllowedDirResponse {
    allowed_dir: Option<String>,
}

#[derive(serde::Serialize)]
struct ShellRunResponse {
    stdout: String,
    stderr: String,
    exit_code: i32,
    success: bool,
    timed_out: bool,
    truncated: bool,
    duration_ms: u64,
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct CodexDelegateRunRequest {
    prompt: String,
    project_path: String,
    run_id: String,
    output_schema: serde_json::Value,
    timeout_seconds: Option<u64>,
}

#[derive(serde::Serialize, serde::Deserialize, Default)]
struct CodexDelegateCommandResult {
    command: String,
    success: bool,
    exit_code: Option<i32>,
    stdout: Option<String>,
    stderr: Option<String>,
    duration_ms: Option<u64>,
}

#[derive(serde::Serialize)]
struct CodexDelegateRunResponse {
    status: String,
    summary: String,
    changed_files: Vec<String>,
    command_results: Vec<CodexDelegateCommandResult>,
    followup_needed: Vec<String>,
    error: Option<String>,
    stdout: String,
    stderr: String,
    exit_code: i32,
    success: bool,
    timed_out: bool,
}

const SHELL_MAX_OUTPUT_BYTES: usize = 2 * 1024 * 1024;
const SHELL_DEFAULT_TIMEOUT_SECONDS: u64 = 30;
const SHELL_MAX_TIMEOUT_SECONDS: u64 = 120;
const CODEX_DEFAULT_TIMEOUT_SECONDS: u64 = 20 * 60;
const CODEX_MAX_TIMEOUT_SECONDS: u64 = 60 * 60;
const CODEX_STREAM_CAPTURE_MAX_BYTES: usize = 8 * 1024 * 1024;

fn is_delegate_payload(value: &serde_json::Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };

    object.contains_key("status")
        || object.contains_key("summary")
        || object.contains_key("changed_files")
        || object.contains_key("command_results")
        || object.contains_key("followup_needed")
        || object.contains_key("error")
}

fn parse_delegate_payload_text(raw: &str) -> Result<Option<serde_json::Value>, serde_json::Error> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }

    let value = serde_json::from_str::<serde_json::Value>(trimmed);
    match value {
        Ok(parsed) if is_delegate_payload(&parsed) => return Ok(Some(parsed)),
        Ok(_) => {}
        Err(err) if !trimmed.contains('\n') => return Err(err),
        Err(_) => {}
    }

    for line in trimmed.lines().rev() {
        let candidate = line.trim();
        if candidate.is_empty() {
            continue;
        }
        match serde_json::from_str::<serde_json::Value>(candidate) {
            Ok(parsed) if is_delegate_payload(&parsed) => return Ok(Some(parsed)),
            Ok(_) => continue,
            Err(_) => continue,
        }
    }

    let mut saw_json_start = false;
    let mut last_error = None;
    for (start_index, ch) in trimmed.char_indices() {
        if ch != '{' {
            continue;
        }
        saw_json_start = true;
        let candidate = &trimmed[start_index..];
        let mut deserializer = serde_json::Deserializer::from_str(candidate);
        match serde_json::Value::deserialize(&mut deserializer) {
            Ok(parsed) if is_delegate_payload(&parsed) => return Ok(Some(parsed)),
            Ok(_) => continue,
            Err(err) => {
                last_error = Some(err);
            }
        }
    }

    if let Some(err) = last_error {
        return Err(err);
    }

    if saw_json_start {
        return Ok(None);
    }

    Ok(None)
}

fn parse_delegate_payload_jsonl(raw: &str) -> Result<Option<serde_json::Value>, serde_json::Error> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }

    let mut last_error = None;
    for line in trimmed.lines() {
        let candidate = line.trim();
        if candidate.is_empty() {
            continue;
        }

        let event = match serde_json::from_str::<serde_json::Value>(candidate) {
            Ok(value) => value,
            Err(err) => {
                last_error = Some(err);
                continue;
            }
        };

        let mut try_parse_candidate = |text: Option<&str>| -> Option<serde_json::Value> {
            let Some(message_text) = text else {
                return None;
            };
            match parse_delegate_payload_text(message_text) {
                Ok(Some(value)) => Some(value),
                Ok(None) => None,
                Err(err) => {
                    last_error = Some(err);
                    None
                }
            }
        };

        if let Some(value) = try_parse_candidate(
            event
                .get("item")
                .and_then(|item| {
                    item.get("type")
                        .and_then(|value| value.as_str())
                        .filter(|value| *value == "agent_message")
                        .map(|_| item)
                })
                .and_then(|item| item.get("text"))
                .and_then(|value| value.as_str()),
        ) {
            return Ok(Some(value));
        }

        if let Some(value) = try_parse_candidate(
            event
                .get("item")
                .and_then(|item| item.get("text"))
                .and_then(|value| value.as_str()),
        ) {
            return Ok(Some(value));
        }

        if let Some(content_items) = event
            .get("item")
            .and_then(|item| item.get("content"))
            .and_then(|value| value.as_array())
        {
            for content_item in content_items {
                if let Some(value) =
                    try_parse_candidate(content_item.get("text").and_then(|value| value.as_str()))
                {
                    return Ok(Some(value));
                }
            }
        }

        if let Some(value) =
            try_parse_candidate(event.get("output_text").and_then(|value| value.as_str()))
        {
            return Ok(Some(value));
        }

        if let Some(value) = try_parse_candidate(
            event
                .get("response")
                .and_then(|response| response.get("output_text"))
                .and_then(|value| value.as_str()),
        ) {
            return Ok(Some(value));
        }
    }

    if let Some(err) = last_error {
        return Err(err);
    }

    Ok(None)
}

fn apply_delegate_payload(
    value: &serde_json::Value,
    status: &mut String,
    summary: &mut String,
    error: &mut Option<String>,
    changed_files: &mut BTreeSet<String>,
    command_results: &mut Vec<CodexDelegateCommandResult>,
    followup_needed: &mut Vec<String>,
) {
    if let Some(parsed_status) = value.get("status").and_then(|v| v.as_str()) {
        *status = parsed_status.to_string();
    }
    if let Some(parsed_summary) = value.get("summary").and_then(|v| v.as_str()) {
        *summary = parsed_summary.to_string();
    }
    if let Some(parsed_error) = value.get("error").and_then(|v| v.as_str()) {
        *error = Some(parsed_error.to_string());
    }
    if let Some(files) = value.get("changed_files").and_then(|v| v.as_array()) {
        for file in files {
            if let Some(item) = file.as_str() {
                let normalized = item.trim().replace('\\', "/");
                if !normalized.is_empty() {
                    changed_files.insert(normalized);
                }
            }
        }
    }
    if let Some(items) = value.get("followup_needed").and_then(|v| v.as_array()) {
        for item in items {
            if let Some(text) = item.as_str() {
                followup_needed.push(text.to_string());
            }
        }
    }
    if let Some(items) = value.get("command_results").and_then(|v| v.as_array()) {
        for item in items {
            let parsed = serde_json::from_value::<CodexDelegateCommandResult>(item.clone())
                .unwrap_or_else(|_| CodexDelegateCommandResult::default());
            command_results.push(parsed);
        }
    }
}

fn summarize_missing_payload(stdout: &str, stderr: &str, exit_code: i32) -> String {
    let stderr_trimmed = stderr.trim();
    if !stderr_trimmed.is_empty() {
        let excerpt = stderr_trimmed
            .lines()
            .rev()
            .find(|line| !line.trim().is_empty())
            .unwrap_or(stderr_trimmed);
        return format!(
            "codex delegate exited without final payload (exit {exit_code}): {excerpt}"
        );
    }

    let stdout_trimmed = stdout.trim();
    if !stdout_trimmed.is_empty() {
        let excerpt = stdout_trimmed
            .lines()
            .rev()
            .find(|line| !line.trim().is_empty())
            .unwrap_or(stdout_trimmed);
        return format!("codex delegate exited without final payload (exit {exit_code}); last stdout: {excerpt}");
    }

    format!("codex delegate exited without final payload (exit {exit_code})")
}

#[cfg(test)]
mod tests {
    use super::{
        is_delegate_payload, parse_delegate_payload_jsonl, parse_delegate_payload_text,
        summarize_missing_payload,
    };
    use serde_json::json;

    #[test]
    fn detects_delegate_payload_shape() {
        assert!(is_delegate_payload(&json!({ "status": "succeeded" })));
        assert!(is_delegate_payload(&json!({ "changed_files": [] })));
        assert!(!is_delegate_payload(&json!({ "foo": "bar" })));
    }

    #[test]
    fn parses_payload_from_plain_json_text() {
        let value = parse_delegate_payload_text(r#"{"status":"succeeded","summary":"done"}"#)
            .expect("parse ok")
            .expect("payload present");
        assert_eq!(
            value.get("status").and_then(|item| item.as_str()),
            Some("succeeded")
        );
        assert_eq!(
            value.get("summary").and_then(|item| item.as_str()),
            Some("done")
        );
    }

    #[test]
    fn parses_payload_from_last_stdout_line() {
        let value = parse_delegate_payload_text(
            "thinking...\n{\"status\":\"failed\",\"error\":\"boom\"}\n",
        )
        .expect("parse ok")
        .expect("payload present");
        assert_eq!(
            value.get("status").and_then(|item| item.as_str()),
            Some("failed")
        );
        assert_eq!(
            value.get("error").and_then(|item| item.as_str()),
            Some("boom")
        );
    }

    #[test]
    fn parses_pretty_json_payload_with_trailing_logs() {
        let value = parse_delegate_payload_text(
            "{\n  \"status\": \"succeeded\",\n  \"summary\": \"done\"\n}\ntrailing logs\n",
        )
        .expect("parse ok")
        .expect("payload present");
        assert_eq!(
            value.get("status").and_then(|item| item.as_str()),
            Some("succeeded")
        );
        assert_eq!(
            value.get("summary").and_then(|item| item.as_str()),
            Some("done")
        );
    }

    #[test]
    fn parses_delegate_payload_from_jsonl_agent_message() {
        let value = parse_delegate_payload_jsonl(
      "{\"type\":\"thread.started\",\"thread_id\":\"abc\"}\n{\"type\":\"item.completed\",\"item\":{\"id\":\"item_0\",\"type\":\"agent_message\",\"text\":\"{\\\"status\\\":\\\"succeeded\\\",\\\"summary\\\":\\\"probe\\\",\\\"changed_files\\\":[],\\\"command_results\\\":[],\\\"followup_needed\\\":[],\\\"error\\\":null}\"}}\n",
    )
    .expect("parse ok")
    .expect("payload present");
        assert_eq!(
            value.get("status").and_then(|item| item.as_str()),
            Some("succeeded")
        );
        assert_eq!(
            value.get("summary").and_then(|item| item.as_str()),
            Some("probe")
        );
    }

    #[test]
    fn parses_delegate_payload_from_jsonl_item_content_text() {
        let value = parse_delegate_payload_jsonl(
      "{\"type\":\"item.completed\",\"item\":{\"id\":\"item_1\",\"type\":\"assistant_message\",\"content\":[{\"type\":\"output_text\",\"text\":\"{\\\"status\\\":\\\"failed\\\",\\\"summary\\\":\\\"need retry\\\",\\\"changed_files\\\":[],\\\"command_results\\\":[],\\\"followup_needed\\\":[],\\\"error\\\":\\\"boom\\\"}\"}]}}\n",
    )
    .expect("parse ok")
    .expect("payload present");
        assert_eq!(
            value.get("status").and_then(|item| item.as_str()),
            Some("failed")
        );
        assert_eq!(
            value.get("error").and_then(|item| item.as_str()),
            Some("boom")
        );
    }

    #[test]
    fn missing_payload_summary_prefers_stderr_excerpt() {
        let summary = summarize_missing_payload("stdout text", "error: delegate crashed\nstack", 1);
        assert!(summary.contains("exit 1"));
        assert!(summary.contains("stack"));
    }
}

fn split_command(input: &str) -> Result<Vec<String>, String> {
    let mut tokens: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut chars = input.chars().peekable();
    let mut in_quote: Option<char> = None;

    while let Some(ch) = chars.next() {
        match in_quote {
            Some(q) => {
                if ch == q {
                    in_quote = None;
                } else if ch == '\\' && q == '"' {
                    if let Some(next) = chars.next() {
                        current.push(next);
                    } else {
                        current.push('\\');
                    }
                } else {
                    current.push(ch);
                }
            }
            None => {
                if ch == '"' || ch == '\'' {
                    in_quote = Some(ch);
                } else if ch.is_whitespace() {
                    if !current.is_empty() {
                        tokens.push(std::mem::take(&mut current));
                    }
                } else if ch == '\\' {
                    if let Some(next) = chars.next() {
                        current.push(next);
                    }
                } else {
                    current.push(ch);
                }
            }
        }
    }

    if in_quote.is_some() {
        return Err("unterminated quote in command".to_string());
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    if tokens.is_empty() {
        return Err("empty command".to_string());
    }
    Ok(tokens)
}

fn contains_shell_meta(command: &str) -> bool {
    command
        .chars()
        .any(|c| matches!(c, ';' | '|' | '&' | '`' | '$' | '>' | '<' | '\n' | '\r'))
}

fn static_allowed_executables() -> HashSet<&'static str> {
    HashSet::from([
        "pwd", "date", "echo", "whoami", "hostname", "uname", "uptime", "ls", "cat", "head",
        "tail", "wc", "diff", "tree", "file", "du", "df", "stat", "readlink", "basename",
        "dirname", "realpath", "find", "grep", "git", "node", "npm", "npx", "pnpm", "yarn", "bun",
        "python", "python3", "uv", "pytest", "cargo",
    ])
}

fn static_allowed_git_subcommands() -> HashSet<&'static str> {
    HashSet::from([
        "status",
        "log",
        "diff",
        "show",
        "branch",
        "rev-parse",
        "remote",
        "describe",
    ])
}

fn build_effective_allowlist(
    static_set: &HashSet<&'static str>,
    provided: Option<Vec<String>>,
) -> HashSet<String> {
    match provided {
        Some(values) if !values.is_empty() => {
            let mut effective = HashSet::new();
            for value in values {
                let normalized = value.trim();
                if !normalized.is_empty() && static_set.contains(normalized) {
                    effective.insert(normalized.to_string());
                }
            }
            effective
        }
        _ => static_set.iter().map(|item| (*item).to_string()).collect(),
    }
}

fn decode_and_truncate(bytes: &[u8], max_bytes: usize) -> (String, bool) {
    if bytes.len() <= max_bytes {
        return (String::from_utf8_lossy(bytes).to_string(), false);
    }

    let mut text = String::from_utf8_lossy(&bytes[..max_bytes]).to_string();
    text.push_str(&format!("\n... [truncated at {max_bytes}B]"));
    (text, true)
}

fn decode_tail_and_truncate(bytes: &[u8], max_bytes: usize) -> (String, bool) {
    if bytes.len() <= max_bytes {
        return (String::from_utf8_lossy(bytes).to_string(), false);
    }

    let omitted = bytes.len().saturating_sub(max_bytes);
    let tail = &bytes[omitted..];
    let mut text = format!("... [truncated first {omitted}B]\n");
    text.push_str(&String::from_utf8_lossy(tail));
    (text, true)
}

fn read_stream_tail<R: Read + Send + 'static>(
    mut reader: R,
    max_bytes: usize,
) -> JoinHandle<Result<Vec<u8>, String>> {
    std::thread::spawn(move || {
        let mut output = Vec::new();
        let mut chunk = [0_u8; 8192];

        loop {
            match reader.read(&mut chunk) {
                Ok(0) => break,
                Ok(size) => {
                    output.extend_from_slice(&chunk[..size]);
                    if output.len() > max_bytes {
                        let overflow = output.len() - max_bytes;
                        output.drain(0..overflow);
                    }
                }
                Err(err) => return Err(format!("{err}")),
            }
        }

        Ok(output)
    })
}

fn join_stream_tail(
    handle: JoinHandle<Result<Vec<u8>, String>>,
    stream_name: &str,
) -> Result<Vec<u8>, String> {
    match handle.join() {
        Ok(Ok(bytes)) => Ok(bytes),
        Ok(Err(err)) => Err(format!("{stream_name} stream read failed: {err}")),
        Err(_) => Err(format!("{stream_name} stream reader panicked")),
    }
}

fn resolve_working_directory(cwd: Option<&str>) -> Result<Option<PathBuf>, String> {
    let Some(raw) = cwd else {
        return Ok(None);
    };

    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }

    let path = PathBuf::from(trimmed)
        .canonicalize()
        .map_err(|e| format!("invalid cwd: {e}"))?;
    if !path.is_dir() {
        return Err("cwd is not a directory".to_string());
    }
    Ok(Some(path))
}

fn parse_git_status_paths(text: &str) -> Vec<String> {
    let mut files = Vec::new();
    for line in text.lines() {
        if line.len() < 4 {
            continue;
        }
        let raw = line[3..].trim();
        if raw.is_empty() {
            continue;
        }
        let normalized = raw
            .rsplit(" -> ")
            .next()
            .unwrap_or(raw)
            .trim()
            .replace('\\', "/");
        if !normalized.is_empty() {
            files.push(normalized);
        }
    }
    files
}

fn git_changed_files(cwd: &Path) -> Vec<String> {
    let output = Command::new("git")
        .current_dir(cwd)
        .args(["status", "--porcelain"])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output();

    match output {
        Ok(result) if result.status.success() => {
            parse_git_status_paths(&String::from_utf8_lossy(&result.stdout))
        }
        _ => Vec::new(),
    }
}

fn normalize_relative_path(rel: &str) -> Result<PathBuf, String> {
    let rel_path = Path::new(rel);
    if rel_path.is_absolute() {
        return Err("path must be relative".to_string());
    }
    for component in rel_path.components() {
        if matches!(component, Component::ParentDir) {
            return Err("path must not contain '..'".to_string());
        }
        if matches!(component, Component::RootDir | Component::Prefix(_)) {
            return Err("path must be relative".to_string());
        }
    }
    Ok(rel_path.to_path_buf())
}

fn resolve_sandboxed_path(state: &FsAccessState, rel: &str) -> Result<PathBuf, String> {
    let allowed = state
        .allowed_dir
        .as_ref()
        .ok_or_else(|| "no allowed directory set".to_string())?;
    let allowed_canonical = state
        .allowed_dir_canonical
        .as_ref()
        .ok_or_else(|| "no allowed directory set".to_string())?;

    let rel_path = normalize_relative_path(rel)?;
    let joined = allowed.join(rel_path);
    let joined_canonical = joined
        .canonicalize()
        .map_err(|e| format!("failed to resolve path: {e}"))?;

    if !joined_canonical.starts_with(allowed_canonical) {
        return Err("path is outside allowed directory".to_string());
    }

    Ok(joined_canonical)
}

#[tauri::command]
fn fs_set_allowed_directory(
    state: tauri::State<SharedFsAccessState>,
    dir: String,
) -> Result<AllowedDirResponse, String> {
    let candidate = PathBuf::from(dir);
    let canonical = candidate
        .canonicalize()
        .map_err(|e| format!("invalid directory: {e}"))?;
    if !canonical.is_dir() {
        return Err("invalid directory".to_string());
    }

    let mut guard = state.lock().map_err(|_| "state poisoned".to_string())?;
    guard.allowed_dir = Some(canonical.clone());
    guard.allowed_dir_canonical = Some(canonical.clone());

    Ok(AllowedDirResponse {
        allowed_dir: Some(canonical.to_string_lossy().to_string()),
    })
}

#[tauri::command]
fn fs_get_allowed_directory(
    state: tauri::State<SharedFsAccessState>,
) -> Result<AllowedDirResponse, String> {
    let guard = state.lock().map_err(|_| "state poisoned".to_string())?;
    Ok(AllowedDirResponse {
        allowed_dir: guard
            .allowed_dir
            .as_ref()
            .map(|p| p.to_string_lossy().to_string()),
    })
}

#[tauri::command]
fn fs_clear_allowed_directory(
    state: tauri::State<SharedFsAccessState>,
) -> Result<AllowedDirResponse, String> {
    let mut guard = state.lock().map_err(|_| "state poisoned".to_string())?;
    guard.allowed_dir = None;
    guard.allowed_dir_canonical = None;
    Ok(AllowedDirResponse { allowed_dir: None })
}

#[tauri::command]
fn fs_read_text_file(
    state: tauri::State<SharedFsAccessState>,
    rel_path: String,
) -> Result<String, String> {
    let guard = state.lock().map_err(|_| "state poisoned".to_string())?;
    let path = resolve_sandboxed_path(&guard, &rel_path)?;
    fs::read_to_string(&path).map_err(|e| format!("read failed: {e}"))
}

#[tauri::command]
fn fs_write_text_file(
    state: tauri::State<SharedFsAccessState>,
    rel_path: String,
    content: String,
) -> Result<(), String> {
    let guard = state.lock().map_err(|_| "state poisoned".to_string())?;
    let path = resolve_sandboxed_path(&guard, &rel_path)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("mkdir failed: {e}"))?;
    }
    fs::write(&path, content).map_err(|e| format!("write failed: {e}"))
}

#[tauri::command]
fn fs_list_dir(
    state: tauri::State<SharedFsAccessState>,
    rel_path: String,
) -> Result<Vec<String>, String> {
    let guard = state.lock().map_err(|_| "state poisoned".to_string())?;
    let path = resolve_sandboxed_path(&guard, &rel_path)?;

    let mut names: Vec<String> = vec![];
    for entry in fs::read_dir(&path).map_err(|e| format!("read dir failed: {e}"))? {
        let entry = entry.map_err(|e| format!("read dir failed: {e}"))?;
        let file_name = entry.file_name().to_string_lossy().to_string();
        names.push(file_name);
    }
    names.sort();
    Ok(names)
}

#[tauri::command]
fn shell_run(
    command: String,
    cwd: Option<String>,
    timeout_seconds: Option<u64>,
    allowed_executables: Option<Vec<String>>,
    allowed_git_subcommands: Option<Vec<String>>,
) -> Result<ShellRunResponse, String> {
    let trimmed = command.trim();
    if trimmed.is_empty() {
        return Err("not_supported: empty command".to_string());
    }
    if contains_shell_meta(trimmed) {
        return Err("not_supported: shell metacharacters are not allowed".to_string());
    }

    let tokens = split_command(trimmed)?;
    let executable = tokens
        .first()
        .ok_or_else(|| "not_supported: empty command".to_string())?;

    if executable.contains('/') || executable.contains('\\') {
        return Err("not_supported: executable path is not allowed".to_string());
    }

    let static_execs = static_allowed_executables();
    let effective_execs = build_effective_allowlist(&static_execs, allowed_executables);
    if !effective_execs.contains(executable.as_str()) {
        return Err(format!("not_supported: unsupported command: {executable}"));
    }

    if executable == "git" {
        let sub = tokens.get(1).map(|s| s.as_str()).unwrap_or("");
        let static_git = static_allowed_git_subcommands();
        let effective_git = build_effective_allowlist(&static_git, allowed_git_subcommands);
        if !effective_git.contains(sub) {
            return Err(format!("not_supported: unsupported git subcommand: {sub}"));
        }
    }

    let timeout = timeout_seconds
        .unwrap_or(SHELL_DEFAULT_TIMEOUT_SECONDS)
        .max(1)
        .min(SHELL_MAX_TIMEOUT_SECONDS);
    let working_dir = resolve_working_directory(cwd.as_deref())?;

    let start = Instant::now();
    let mut command_builder = Command::new(executable);
    command_builder
        .args(tokens.iter().skip(1))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(dir) = working_dir.as_ref() {
        command_builder.current_dir(dir);
    }
    let mut child = command_builder
        .spawn()
        .map_err(|e| format!("spawn failed: {e}"))?;

    let mut timed_out = false;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) => {
                if start.elapsed() >= Duration::from_secs(timeout) {
                    timed_out = true;
                    let _ = child.kill();
                    break;
                }
                std::thread::sleep(Duration::from_millis(20));
            }
            Err(e) => return Err(format!("process wait failed: {e}")),
        }
    }

    let output = child
        .wait_with_output()
        .map_err(|e| format!("process output failed: {e}"))?;
    let (stdout, stdout_truncated) = decode_and_truncate(&output.stdout, SHELL_MAX_OUTPUT_BYTES);
    let (stderr, stderr_truncated) = decode_and_truncate(&output.stderr, SHELL_MAX_OUTPUT_BYTES);
    let exit_code = output
        .status
        .code()
        .unwrap_or(if timed_out { -1 } else { 1 });

    Ok(ShellRunResponse {
        stdout,
        stderr,
        exit_code,
        success: exit_code == 0 && !timed_out,
        timed_out,
        truncated: stdout_truncated || stderr_truncated,
        duration_ms: start.elapsed().as_millis() as u64,
    })
}

fn run_codex_delegate_blocking(
    request: CodexDelegateRunRequest,
) -> Result<CodexDelegateRunResponse, String> {
    let project_dir = resolve_working_directory(Some(request.project_path.as_str()))?
        .ok_or_else(|| "project_path is required".to_string())?;
    let timeout = request
        .timeout_seconds
        .unwrap_or(CODEX_DEFAULT_TIMEOUT_SECONDS)
        .max(30)
        .min(CODEX_MAX_TIMEOUT_SECONDS);

    let temp_root = std::env::temp_dir()
        .join("xiyan-orchestrator")
        .join(&request.run_id);
    fs::create_dir_all(&temp_root).map_err(|e| format!("create temp dir failed: {e}"))?;
    let schema_path = temp_root.join("delegate-output-schema.json");
    let output_path = temp_root.join("delegate-last-message.json");
    fs::write(
        &schema_path,
        serde_json::to_vec_pretty(&request.output_schema)
            .map_err(|e| format!("serialize schema failed: {e}"))?,
    )
    .map_err(|e| format!("write schema failed: {e}"))?;

    let before_git = git_changed_files(&project_dir)
        .into_iter()
        .collect::<BTreeSet<String>>();

    let start = Instant::now();
    let mut child = Command::new("codex")
        .arg("exec")
        .arg("--sandbox")
        .arg("workspace-write")
        .arg("--skip-git-repo-check")
        .arg("--ephemeral")
        .arg("--color")
        .arg("never")
        .arg("--json")
        .arg("-C")
        .arg(&project_dir)
        .arg("--output-schema")
        .arg(&schema_path)
        .arg("-o")
        .arg(&output_path)
        .arg(&request.prompt)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("spawn codex failed: {e}"))?;

    let stdout_pipe = child
        .stdout
        .take()
        .ok_or_else(|| "capture codex stdout failed".to_string())?;
    let stderr_pipe = child
        .stderr
        .take()
        .ok_or_else(|| "capture codex stderr failed".to_string())?;
    let stdout_reader = read_stream_tail(stdout_pipe, CODEX_STREAM_CAPTURE_MAX_BYTES);
    let stderr_reader = read_stream_tail(stderr_pipe, CODEX_STREAM_CAPTURE_MAX_BYTES);

    let mut timed_out = false;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) => {
                if start.elapsed() >= Duration::from_secs(timeout) {
                    timed_out = true;
                    let _ = child.kill();
                    break;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => return Err(format!("codex wait failed: {e}")),
        }
    }

    let status = child
        .wait()
        .map_err(|e| format!("codex output failed: {e}"))?;
    let stdout_bytes = join_stream_tail(stdout_reader, "stdout")?;
    let stderr_bytes = join_stream_tail(stderr_reader, "stderr")?;
    let stdout_full = String::from_utf8_lossy(&stdout_bytes).to_string();
    let stderr_full = String::from_utf8_lossy(&stderr_bytes).to_string();
    let (stdout, _) = decode_tail_and_truncate(&stdout_bytes, SHELL_MAX_OUTPUT_BYTES);
    let (stderr, _) = decode_tail_and_truncate(&stderr_bytes, SHELL_MAX_OUTPUT_BYTES);
    let exit_code = status.code().unwrap_or(if timed_out { -1 } else { 1 });

    let after_git = git_changed_files(&project_dir);
    let mut changed_files = after_git
        .into_iter()
        .filter(|item| !before_git.contains(item))
        .collect::<BTreeSet<String>>();

    let mut status = if exit_code == 0 && !timed_out {
        "succeeded".to_string()
    } else {
        "failed".to_string()
    };
    let mut summary = if status == "succeeded" {
        "delegate completed".to_string()
    } else {
        "delegate failed".to_string()
    };
    let mut command_results = Vec::new();
    let mut followup_needed = Vec::new();
    let mut error = None;

    let mut payload_applied = false;
    let mut parse_error = None;

    match parse_delegate_payload_jsonl(&stdout_full) {
        Ok(Some(value)) => {
            apply_delegate_payload(
                &value,
                &mut status,
                &mut summary,
                &mut error,
                &mut changed_files,
                &mut command_results,
                &mut followup_needed,
            );
            payload_applied = true;
        }
        Ok(None) => {}
        Err(e) => {
            parse_error = Some(format!("invalid delegate JSONL output: {e}"));
        }
    }

    if !payload_applied && output_path.exists() {
        let raw = fs::read_to_string(&output_path)
            .map_err(|e| format!("read codex output failed: {e}"))?;
        match parse_delegate_payload_text(&raw) {
            Ok(Some(value)) => {
                apply_delegate_payload(
                    &value,
                    &mut status,
                    &mut summary,
                    &mut error,
                    &mut changed_files,
                    &mut command_results,
                    &mut followup_needed,
                );
                payload_applied = true;
            }
            Ok(None) => {
                parse_error =
                    Some("delegate output file did not contain a structured payload".to_string());
            }
            Err(e) => {
                parse_error = Some(format!("invalid delegate JSON output: {e}"));
            }
        }
    }

    if !payload_applied {
        for candidate in [&stdout_full, &stderr_full] {
            match parse_delegate_payload_text(candidate) {
                Ok(Some(value)) => {
                    apply_delegate_payload(
                        &value,
                        &mut status,
                        &mut summary,
                        &mut error,
                        &mut changed_files,
                        &mut command_results,
                        &mut followup_needed,
                    );
                    payload_applied = true;
                    parse_error = None;
                    break;
                }
                Ok(None) => {}
                Err(e) => {
                    parse_error = Some(format!("invalid delegate JSON output: {e}"));
                }
            }
        }
    }

    if !payload_applied && error.is_none() {
        error =
            Some(parse_error.unwrap_or_else(|| {
                summarize_missing_payload(&stdout_full, &stderr_full, exit_code)
            }));
    }

    if timed_out && error.is_none() {
        error = Some(format!("codex delegate timed out after {timeout}s"));
    }
    if error.is_some() {
        status = "failed".to_string();
    }

    Ok(CodexDelegateRunResponse {
        status,
        summary,
        changed_files: changed_files.into_iter().collect(),
        command_results,
        followup_needed,
        error,
        stdout,
        stderr,
        exit_code,
        success: exit_code == 0 && !timed_out,
        timed_out,
    })
}

#[tauri::command]
async fn codex_run_delegate(
    request: CodexDelegateRunRequest,
) -> Result<CodexDelegateRunResponse, String> {
    tauri::async_runtime::spawn_blocking(move || run_codex_delegate_blocking(request))
        .await
        .map_err(|e| format!("codex delegate join failed: {e}"))?
}

// ===== Pet (Desktop Pet) Commands =====

#[derive(serde::Serialize)]
struct PetStatusResponse {
    visible: bool,
}

#[tauri::command]
async fn pet_show(app: tauri::AppHandle) -> Result<PetStatusResponse, String> {
    match app.get_webview_window("pet") {
        Some(win) => {
            win.show().map_err(|e| format!("show pet: {e}"))?;
            win.set_focus().map_err(|e| format!("focus pet: {e}"))?;
        }
        None => {
            let mut candidates = Vec::new();
            if let Ok(resource_dir) = app.path().resource_dir() {
                candidates.push(resource_dir.join("pet").join("index.html"));
            }
            candidates.push(
                std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("pet")
                    .join("index.html"),
            );

            let pet_html = candidates.into_iter().find(|p| p.exists()).ok_or_else(|| {
                "pet page not found (tried resource_dir and CARGO_MANIFEST_DIR)".to_string()
            })?;

            let url = format!(
                "file://{}",
                pet_html
                    .to_string_lossy()
                    .replace(' ', "%20")
                    .replace('#', "%23")
            );

            let build_result = tauri::WebviewWindowBuilder::new(
                &app,
                "pet",
                tauri::WebviewUrl::External(url.parse().unwrap()),
            )
            .title("INTP 小紫人")
            .inner_size(280.0, 380.0)
            .decorations(false)
            .always_on_top(true)
            .resizable(false)
            .skip_taskbar(true)
            .build();

            match build_result {
                Ok(win) => {
                    win.show().map_err(|e| format!("show pet: {e}"))?;
                    win.set_focus().map_err(|e| format!("focus pet: {e}"))?;
                }
                Err(err) => {
                    let err_text = err.to_string();
                    if err_text.contains("already exists") {
                        if let Some(win) = app.get_webview_window("pet") {
                            win.show().map_err(|e| format!("show pet: {e}"))?;
                            win.set_focus().map_err(|e| format!("focus pet: {e}"))?;
                            return Ok(PetStatusResponse { visible: true });
                        }
                    }
                    return Err(format!("create pet window: {err}"));
                }
            }
        }
    }
    Ok(PetStatusResponse { visible: true })
}

#[tauri::command]
async fn pet_hide(app: tauri::AppHandle) -> Result<PetStatusResponse, String> {
    if let Some(win) = app.get_webview_window("pet") {
        win.hide().map_err(|e| format!("hide pet: {e}"))?;
    }
    Ok(PetStatusResponse { visible: false })
}

#[tauri::command]
async fn pet_close(app: tauri::AppHandle) -> Result<PetStatusResponse, String> {
    if let Some(win) = app.get_webview_window("pet") {
        // Best-effort: hide first to ensure it disappears immediately,
        // then request close to fully exit the window.
        let _ = win.hide();
        win.close().map_err(|e| format!("close pet: {e}"))?;
    }
    Ok(PetStatusResponse { visible: false })
}

#[tauri::command]
async fn pet_is_visible(app: tauri::AppHandle) -> Result<PetStatusResponse, String> {
    let visible = match app.get_webview_window("pet") {
        Some(win) => win
            .is_visible()
            .map_err(|e| format!("check visible: {e}"))?,
        None => false,
    };
    Ok(PetStatusResponse { visible })
}

#[tauri::command]
async fn pet_send_message(app: tauri::AppHandle, text: String) -> Result<(), String> {
    if let Some(pet_win) = app.get_webview_window("pet") {
        pet_win
            .emit("pet-message", serde_json::json!({ "text": text }))
            .map_err(|e| format!("send to pet: {e}"))?;
    }
    Ok(())
}

#[tauri::command]
async fn pet_toggle(app: tauri::AppHandle) -> Result<PetStatusResponse, String> {
    let currently_visible = match app.get_webview_window("pet") {
        Some(win) => win
            .is_visible()
            .map_err(|e| format!("check visible: {e}"))?,
        None => false,
    };

    if currently_visible {
        if let Some(win) = app.get_webview_window("pet") {
            win.hide().map_err(|e| format!("hide pet: {e}"))?;
        }
        Ok(PetStatusResponse { visible: false })
    } else {
        pet_show(app).await
    }
}

fn main() {
    tauri::Builder::default()
        .manage(Mutex::new(FsAccessState::default()))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            // FS commands
            fs_set_allowed_directory,
            fs_get_allowed_directory,
            fs_clear_allowed_directory,
            fs_read_text_file,
            fs_write_text_file,
            fs_list_dir,
            shell_run,
            codex_run_delegate,
            // Pet commands
            pet_show,
            pet_hide,
            pet_close,
            pet_is_visible,
            pet_toggle,
            pet_send_message,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
