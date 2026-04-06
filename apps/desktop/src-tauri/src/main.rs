#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Emitter, Manager};
use std::{
  fs,
  path::{Component, Path, PathBuf},
  sync::Mutex,
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
      // Resolve absolute path to pet/index.html
      // Works in both dev mode and production
      let mut pet_html = app
        .path()
        .resource_dir()
        .map_err(|e| format!("resource dir: {e}"))?;
      pet_html.push("pet");
      pet_html.push("index.html");

      if !pet_html.exists() {
        return Err(format!("pet page not found at {:?}", pet_html));
      }

      let url = format!(
        "file://{}",
        pet_html.to_string_lossy().replace(' ', "%20").replace('#', "%23")
      );

      tauri::WebviewWindowBuilder::new(&app, "pet", tauri::WebviewUrl::External(url.parse().unwrap()))
        .title("INTP 小紫人")
        .inner_size(280.0, 380.0)
        .decorations(false)
        .always_on_top(true)
        .resizable(false)
        .skip_taskbar(true)
        .build()
        .map_err(|e| format!("create pet window: {e}"))?;
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
      // Pet commands
      pet_show,
      pet_hide,
      pet_is_visible,
      pet_toggle,
      pet_send_message,
    ])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
