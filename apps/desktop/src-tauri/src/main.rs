#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Emitter, Manager};
use std::{
  collections::HashSet,
  fs,
  path::{Component, Path, PathBuf},
  process::{Command, Stdio},
  sync::Mutex,
  time::{Duration, Instant},
};

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

const SHELL_MAX_OUTPUT_BYTES: usize = 2 * 1024 * 1024;
const SHELL_DEFAULT_TIMEOUT_SECONDS: u64 = 30;
const SHELL_MAX_TIMEOUT_SECONDS: u64 = 120;

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
    "pwd",
    "date",
    "echo",
    "whoami",
    "hostname",
    "uname",
    "uptime",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "diff",
    "tree",
    "file",
    "du",
    "df",
    "stat",
    "readlink",
    "basename",
    "dirname",
    "realpath",
    "find",
    "grep",
    "git",
  ])
}

fn static_allowed_git_subcommands() -> HashSet<&'static str> {
  HashSet::from(["status", "log", "diff", "show", "branch", "rev-parse", "remote", "describe"])
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
fn fs_set_allowed_directory(state: tauri::State<SharedFsAccessState>, dir: String) -> Result<AllowedDirResponse, String> {
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
fn fs_get_allowed_directory(state: tauri::State<SharedFsAccessState>) -> Result<AllowedDirResponse, String> {
  let guard = state.lock().map_err(|_| "state poisoned".to_string())?;
  Ok(AllowedDirResponse {
    allowed_dir: guard.allowed_dir.as_ref().map(|p| p.to_string_lossy().to_string()),
  })
}

#[tauri::command]
fn fs_clear_allowed_directory(state: tauri::State<SharedFsAccessState>) -> Result<AllowedDirResponse, String> {
  let mut guard = state.lock().map_err(|_| "state poisoned".to_string())?;
  guard.allowed_dir = None;
  guard.allowed_dir_canonical = None;
  Ok(AllowedDirResponse { allowed_dir: None })
}

#[tauri::command]
fn fs_read_text_file(state: tauri::State<SharedFsAccessState>, rel_path: String) -> Result<String, String> {
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
fn fs_list_dir(state: tauri::State<SharedFsAccessState>, rel_path: String) -> Result<Vec<String>, String> {
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

  let start = Instant::now();
  let mut child = Command::new(executable)
    .args(tokens.iter().skip(1))
    .stdout(Stdio::piped())
    .stderr(Stdio::piped())
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
  let exit_code = output.status.code().unwrap_or(if timed_out { -1 } else { 1 });

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
      candidates.push(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("pet").join("index.html"));

      let pet_html = candidates
        .into_iter()
        .find(|p| p.exists())
        .ok_or_else(|| "pet page not found (tried resource_dir and CARGO_MANIFEST_DIR)".to_string())?;

      let url = format!(
        "file://{}",
        pet_html.to_string_lossy().replace(' ', "%20").replace('#', "%23")
      );

      let build_result = tauri::WebviewWindowBuilder::new(&app, "pet", tauri::WebviewUrl::External(url.parse().unwrap()))
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
    Some(win) => win.is_visible().map_err(|e| format!("check visible: {e}"))?,
    None => false,
  };
  Ok(PetStatusResponse { visible })
}

#[tauri::command]
async fn pet_send_message(
  app: tauri::AppHandle,
  text: String,
) -> Result<(), String> {
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
    Some(win) => win.is_visible().map_err(|e| format!("check visible: {e}"))?,
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
